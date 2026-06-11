import itertools
import logging
import re
from typing import Annotated, Any, ClassVar, Optional

from markupsafe import Markup
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from .registry import Registry
from .renderer import Renderer
from .assets import RenderSession

logger = logging.getLogger("pyjinhx")
logger.setLevel(logging.WARNING)

_auto_id_counter = itertools.count(1)

_ATTR_NAME_RE = re.compile(r"[A-Za-z@:][A-Za-z0-9_.:@-]*")


def _auto_id() -> str:
    """Generate a process-unique component id (``px-<n>``)."""
    return f"px-{next(_auto_id_counter)}"


def validate_attr_value(value: str) -> str:
    """Reject values that could break out of a double-quoted HTML attribute.

    The renderer unescapes final markup by design, so attribute safety is
    enforced at construction time. Post-construction mutation bypasses this.
    """
    if '"' in value:
        raise ValueError('attribute values must not contain \'"\'')
    return value


def validate_extra_attrs(value: dict[str, str]) -> dict[str, str]:
    """Reject attribute names/values that could break out of an HTML attribute."""
    for name, attr_value in value.items():
        if not _ATTR_NAME_RE.fullmatch(name):
            raise ValueError(f"extra_attrs name {name!r} is not a valid attribute name")
        validate_attr_value(attr_value)
    return value


AttrValue = Annotated[str, AfterValidator(validate_attr_value)]
ExtraAttrs = Annotated[dict[str, str], AfterValidator(validate_extra_attrs)]


class NestedComponentWrapper(BaseModel):
    """
    A wrapper for nested components. Enables access to the component's properties and rendered HTML.

    Attributes:
        html: The rendered HTML string of the nested component.
        props: The original component instance, or None for template-only components.
    """

    html: str
    props: Optional["BaseComponent"]

    def __str__(self) -> Markup:
        return self.html


class BaseComponent(BaseModel):
    """
    Base class for defining reusable UI components with Pydantic validation and Jinja2 templating.

    Subclasses are automatically registered and can be rendered using their corresponding
    HTML/Jinja templates. Components support nested composition, automatic JavaScript collection,
    and can be used directly in Jinja templates via the `__html__` protocol.

    Attributes:
        id: Unique identifier for the component instance.
        js: Paths to additional JavaScript files to include when rendering.
    """

    model_config = ConfigDict(extra="allow")

    _pjx_framework: ClassVar[bool] = True

    # Field that children of a PascalCase tag map into (e.g. <Card>text</Card>).
    # Components without a `content` field can point this at their text slot.
    _pjx_children_field: ClassVar[str] = "content"

    id: str = Field(
        default_factory=_auto_id,
        description="The unique ID for this component. Auto-generated when omitted.",
    )
    js: list[str] = Field(
        default_factory=list,
        description="List of paths to extra JavaScript files to include.",
    )
    css: list[str] = Field(
        default_factory=list,
        description="List of paths to extra CSS files to include.",
    )

    @field_validator("id", mode="before")
    def validate_id(cls, v: object) -> str:
        if not v:
            return _auto_id()
        return str(v)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register the component class on subclass definition."""
        super().__init_subclass__(**kwargs)
        component_bases = [
            base
            for base in cls.__bases__
            if issubclass(base, BaseComponent) and "_pjx_framework" not in base.__dict__
        ]
        if len(component_bases) > 1:
            names = ", ".join(base.__name__ for base in component_bases)
            raise TypeError(
                f"{cls.__name__}: subclass one component at a time; got {names}"
            )
        Registry.register_class(cls)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        Registry.register_instance(self)

    def __html__(self) -> Markup:
        """
        Render the component when used in a Jinja template context.

        Enables cleaner template syntax: `{{ component }}` instead of `{{ component.render() }}`.

        Returns:
            The rendered HTML as a Markup object.
        """
        return self._render()

    def _wrap_component_value(
        self,
        field_value: Any,
        *,
        context: dict[str, Any],
        renderer: Renderer,
        session: RenderSession,
    ) -> Any:
        if isinstance(field_value, BaseComponent):
            _guard_key = (type(field_value).__name__, field_value.id)
            if _guard_key in session.rendering:
                # Already on the render stack: rendering it here would recurse
                # forever, so the cyclic reference renders empty instead.
                logger.warning(
                    "render cycle suppressed: <%s id=%s> is already being rendered",
                    type(field_value).__name__,
                    field_value.id,
                )
                return NestedComponentWrapper(html="", props=field_value)
            return NestedComponentWrapper(
                html=field_value._render(
                    base_context=context,
                    _renderer=renderer,
                    _session=session,
                ),
                props=field_value,
            )
        if isinstance(field_value, list):
            processed_list = []
            for item in field_value:
                if isinstance(item, BaseComponent):
                    processed_list.append(
                        self._wrap_component_value(
                            item,
                            context=context,
                            renderer=renderer,
                            session=session,
                        )
                    )
                else:
                    processed_list.append(item)
            return processed_list if processed_list else field_value
        if isinstance(field_value, dict):
            processed_dict = {}
            for key, value in field_value.items():
                if isinstance(value, BaseComponent):
                    processed_dict[key] = self._wrap_component_value(
                        value,
                        context=context,
                        renderer=renderer,
                        session=session,
                    )
                else:
                    processed_dict[key] = value
            return processed_dict if processed_dict else field_value
        return field_value

    def _update_context_(
        self,
        context: dict[str, Any],
        field_name: str,
        field_value: Any,
        *,
        renderer: Renderer,
        session: RenderSession,
    ) -> dict[str, Any]:
        """Updates the context with rendered components by their ID."""
        wrapped = self._wrap_component_value(
            field_value,
            context=context,
            renderer=renderer,
            session=session,
        )
        if wrapped is not field_value:
            context[field_name] = wrapped
        return context

    def _render(
        self,
        source: str | None = None,
        base_context: dict[str, Any] | None = None,
        *,
        _renderer: Renderer | None = None,
        _session: RenderSession | None = None,
        _template_path: str | None = None,
        emit_assets: bool = True,
        client: object | None = None,
    ) -> Markup:
        renderer = _renderer or Renderer.get_default_renderer()

        is_root = base_context is None and _session is None
        session = _session or renderer.new_session()

        _guard_key = (type(self).__name__, self.id)
        if _guard_key in session.rendering:
            # This component is already being rendered higher up the stack
            # (a self- or ancestor tag reference). Render empty to break the
            # cycle instead of recursing forever.
            logger.warning(
                "render cycle suppressed: <%s id=%s> is already being rendered",
                type(self).__name__,
                self.id,
            )
            return Markup("")
        session.rendering.add(_guard_key)
        try:
            if base_context is None:
                context: dict[str, Any] = self.model_dump()
            else:
                context = {**base_context, **self.model_dump()}

            for field_name in type(self).model_fields.keys():
                field_value = getattr(self, field_name)
                context = self._update_context_(
                    context,
                    field_name,
                    field_value,
                    renderer=renderer,
                    session=session,
                )

            declared_fields = set(type(self).model_fields.keys())
            for field_name, field_value in context.items():
                if field_name in declared_fields:
                    continue
                context = self._update_context_(
                    context,
                    field_name,
                    field_value,
                    renderer=renderer,
                    session=session,
                )

            from pyjinhx.client import ClientBackend, LoadedAssets

            resolved_client = ClientBackend.resolve_client(client)
            loaded_assets = (
                LoadedAssets.parse(resolved_client)
                if resolved_client is not None and emit_assets
                else frozenset()
            )

            return renderer.render_component_with_context(
                self,
                context=context,
                template_source=source,
                template_path=_template_path,
                session=session,
                is_root=is_root,
                collect_component_js=source is None,
                emit_assets=emit_assets,
                loaded_assets=loaded_assets,
                client=resolved_client,
            )
        finally:
            session.rendering.discard(_guard_key)

    def render(self) -> Markup:
        """
        Render this component to HTML using its associated Jinja template.

        The template is auto-discovered based on the component class name (e.g., `MyButton` looks
        for `my_button.html` or `my_button.jinja`). All component fields are available in the
        template context, and nested components are rendered recursively.

        Returns:
            The rendered HTML as a Markup object (safe for direct use in templates).
        """
        return self._render()
