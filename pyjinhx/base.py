import itertools
import logging
import re
from functools import cached_property
from typing import Annotated, Any, ClassVar, Optional

from markupsafe import Markup
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from .context import wrap_context_methods
from .registry import Registry
from .renderer import Renderer
from .assets import RenderSession

logger = logging.getLogger("pyjinhx")
logger.setLevel(logging.WARNING)

_auto_id_counter = itertools.count(1)

_ATTR_NAME_RE = re.compile(r"[A-Za-z@:][A-Za-z0-9_.:@-]*")


def _auto_id() -> str:
    """Generate a process-unique component id (``pjx-<n>``)."""
    return f"pjx-{next(_auto_id_counter)}"


def validate_attr_value(value: str) -> str:
    """Reject values that could break out of a double-quoted HTML attribute.

    The renderer unescapes final markup by design, so attribute safety is
    enforced at construction time. Post-construction mutation bypasses this.
    """
    if '"' in value:
        raise ValueError('attribute values must not contain \'"\'')
    return value


def validate_extra_attrs(value: dict[str, str]) -> dict[str, str]:
    """Reject attribute names/values that could break out of an HTML attribute.

    Values with one quote type are fine: emission picks the other quote
    (see ``render_extra_attrs``). Values with both are inexpressible.
    """
    for name, attr_value in value.items():
        if not _ATTR_NAME_RE.fullmatch(name):
            raise ValueError(f"extra_attrs name {name!r} is not a valid attribute name")
        if '"' in attr_value and "'" in attr_value:
            raise ValueError(
                "attribute values must not contain both '\"' and \"'\""
            )
    return value


AttrValue = Annotated[str, AfterValidator(validate_attr_value)]
ExtraAttrs = Annotated[dict[str, str], AfterValidator(validate_extra_attrs)]


def render_extra_attrs(component: "BaseComponent") -> str:
    """Emit a component's pass-through HTML attributes as ` name="value"` pairs.

    Merges the ``extra_attrs`` dict with stray tag attributes (pydantic extras
    that are plain strings with valid attribute names). Values containing ``"``
    are emitted single-quoted; values containing both quote types raise.
    """
    attrs = dict(getattr(component, "extra_attrs", None) or {})
    children_field = type(component)._pjx_children_field
    for name, value in (component.model_extra or {}).items():
        if name == children_field or not isinstance(value, str):
            continue
        if _ATTR_NAME_RE.fullmatch(name):
            attrs.setdefault(name, value)

    parts = []
    for name, value in attrs.items():
        if '"' in value:
            if "'" in value:
                raise ValueError(
                    f"attribute {name!r} value must not contain both '\"' and \"'\""
                )
            parts.append(f" {name}='{value}'")
        else:
            parts.append(f' {name}="{value}"')
    return "".join(parts)


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


class LazyNestedComponentWrapper:
    """
    A registry peer injected into a render context by id. Same interface as
    `NestedComponentWrapper` (`html`, `props`, string conversion) but renders
    only when a template actually references it.

    Holds the live render session so the deferred render happens inside the
    originating render call and the render-cycle guard still applies.
    """

    def __init__(
        self,
        instance: "BaseComponent",
        context: dict[str, Any],
        *,
        renderer: Renderer,
        session: RenderSession,
    ) -> None:
        self._instance = instance
        self._context = context
        self._renderer = renderer
        self._session = session

    @cached_property
    def html(self) -> str:
        return self._instance._render(
            base_context=self._context,
            _renderer=self._renderer,
            _session=self._session,
        )

    @property
    def props(self) -> "BaseComponent":
        return self._instance

    def __html__(self) -> Markup:
        return Markup(self.html)

    def __str__(self) -> str:
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

    # Field that children of a PascalCase tag map into (e.g. <PJXCard>text</PJXCard>).
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

    def __init_subclass__(cls, pjx_replace: bool = False, **kwargs: Any) -> None:
        """
        Register the component class on subclass definition.

        ``pjx_replace=True`` intentionally shadows a same-named component from
        another module (e.g. a builtin): ``class PJXAvatar(BaseComponent, pjx_replace=True)``.
        """
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
        Registry.register_class(cls, replace=pjx_replace)
        wrap_context_methods(cls)

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
                if isinstance(field_value, BaseComponent):
                    # Registry peers injected by id. Rendering them eagerly
                    # multiplied across every registered instance (issue #67),
                    # so defer until a template actually references them.
                    context[field_name] = LazyNestedComponentWrapper(
                        field_value, context, renderer=renderer, session=session
                    )
                    continue
                context = self._update_context_(
                    context,
                    field_name,
                    field_value,
                    renderer=renderer,
                    session=session,
                )

            if type(self).__module__.startswith("pyjinhx.builtins"):
                context["extra_attrs_html"] = render_extra_attrs(self)

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

        The template is auto-discovered from the component class name (e.g.,
        ``MyButton`` looks for ``my_button.html``/``my_button.jinja``). All
        fields are available in the template context, and nested components
        render recursively.

        When mutations occurred in the current request scope and a client
        backend is active, OOB swaps for the dirtied mounted reactive regions
        are appended (once per scope). Returns plain rendered HTML otherwise.
        """
        from pyjinhx.reactive import _finish_with_oob

        return _finish_with_oob(self._render())
