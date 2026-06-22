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

    Belt-and-suspenders construction-time guard complementing autoescape:
    autoescape handles text content, but attribute quoting is structural and
    must be caught before the value reaches the template.
    Post-construction mutation bypasses this check.
    """
    if '"' in value:
        raise ValueError('attribute values must not contain \'"\'')
    return value


def validate_extra_attrs(value: dict[str, str]) -> dict[str, str]:
    """Reject attribute names/values that could break out of an HTML attribute.

    Values with one quote type are fine: emission picks the other quote
    (see ``pyjinhx.root_attrs``). Values with both are inexpressible.
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


class PjxSlot:
    """Marker (in a field's Annotated metadata) for a raw-HTML slot field —
    its string value is emitted unescaped. Use via the ``Slot`` alias."""


# Slot is defined after BaseComponent (forward-ref resolved at class definition time)


def _is_slot_field(cls: type, field_name: str) -> bool:
    if field_name == getattr(cls, "_pjx_children_field", None):
        return True
    field = cls.model_fields.get(field_name)
    return bool(field) and any(isinstance(m, PjxSlot) for m in field.metadata)


def _wrap_slot_value(value: Any) -> Any:
    """Wrap a slot field's string value(s) as ``markupsafe.Markup`` so they
    pass through Jinja unescaped. Recurses into list/dict slot collections
    (e.g. ``PJXDropdown.items``); non-string elements (nested components) are
    left untouched and render raw via their own ``__html__``."""
    if isinstance(value, str):
        return Markup(value)
    if isinstance(value, list):
        return [_wrap_slot_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _wrap_slot_value(item) for key, item in value.items()}
    return value


def collect_extra_attrs(component: "BaseComponent") -> dict[str, str]:
    """Collect a component's pass-through HTML attributes as an ordered dict.

    Merges the ``extra_attrs`` dict with stray tag attributes (pydantic extras
    that are plain strings with valid attribute names). Serialization and quote
    handling happen at injection time (see ``pyjinhx.root_attrs``).
    """
    attrs = dict(getattr(component, "extra_attrs", None) or {})
    children_field = type(component)._pjx_children_field
    for name, value in (component.model_extra or {}).items():
        if name == children_field or not isinstance(value, str):
            continue
        if _ATTR_NAME_RE.fullmatch(name):
            attrs.setdefault(name, value)
    return attrs


class NestedComponentWrapper(BaseModel):
    """
    A wrapper for nested components. Enables access to the component's properties and rendered HTML.

    Attributes:
        html: The rendered HTML string of the nested component.
        props: The original component instance, or None for template-only components.
    """

    html: str
    props: Optional["BaseComponent"]

    def __html__(self) -> Markup:
        return Markup(self.html)

    def __str__(self) -> str:
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

    # Tag name for html-only components synthesized via `component(name)`. When
    # set, the template is resolved by scanning the default env at render time.
    _pjx_template: ClassVar[str | None] = None

    # True on classes built dynamically (props_header or component() factory).
    # Distinct from _pjx_template because file-backed classes may also set that.
    _pjx_classless: ClassVar[bool] = False

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

    def _build_template_context(
        self,
        base_context: dict[str, Any] | None = None,
        *,
        renderer: Renderer | None = None,
        session: RenderSession | None = None,
    ) -> dict[str, Any]:
        """Build the template context dict for this component.

        Merges ``base_context`` with the component's field values, runs
        ``_update_context_`` for each declared field, and wraps slot-field
        string values as ``markupsafe.Markup`` (so they pass through Jinja
        unescaped once autoescape is enabled).

        Safe to call outside an active request scope (renderer and session
        default to the process-level defaults).
        """
        _renderer = renderer or Renderer.get_default_renderer()
        _session = session or _renderer.new_session()

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
                renderer=_renderer,
                session=_session,
            )
            if _is_slot_field(type(self), field_name):
                context[field_name] = _wrap_slot_value(context.get(field_name))

        declared_fields = set(type(self).model_fields.keys())
        for field_name, field_value in context.items():
            if field_name in declared_fields:
                continue
            if isinstance(field_value, BaseComponent):
                # Registry peers injected by id. Rendering them eagerly
                # multiplied across every registered instance (issue #67),
                # so defer until a template actually references them.
                context[field_name] = LazyNestedComponentWrapper(
                    field_value, context, renderer=_renderer, session=_session
                )
                continue
            context = self._update_context_(
                context,
                field_name,
                field_value,
                renderer=_renderer,
                session=_session,
            )
            # The children field can arrive here as a pydantic extra (classless /
            # undeclared `content`); slot-wrap it too so it renders raw without
            # `| safe`, matching a declared children field (#125).
            if _is_slot_field(type(self), field_name):
                context[field_name] = _wrap_slot_value(context.get(field_name))

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
            context = self._build_template_context(
                base_context, renderer=renderer, session=session
            )

            from pyjinhx.client import ClientBackend

            resolved_client = ClientBackend.resolve_client(client)

            return renderer.render_component_with_context(
                self,
                context=context,
                template_source=source,
                template_path=_template_path,
                session=session,
                is_root=is_root,
                collect_component_js=source is None,
                emit_assets=emit_assets,
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


Slot = Annotated[str | BaseComponent, PjxSlot()]


def component(name: str) -> type[BaseComponent]:
    """
    Reference an html-only component (a template with no hand-written class).

    ``component("Card")`` returns a class whose template (``card.html``) is
    resolved by scanning the default environment at render time, so it works
    even if the default environment isn't set yet at call time::

        Card = component("Card")
        Card(title="Hi", content="body").render()

    Idempotent: calling it twice returns the same class, and it never shadows
    an already-declared component of the same name.
    """
    from .tags import RE_PASCAL_CASE_TAG_NAME

    if not RE_PASCAL_CASE_TAG_NAME.match(name):
        raise ValueError(f"component name {name!r} must be PascalCase")
    existing = Registry.get_class(name)
    if existing is not None:
        return existing

    # If the template is resolvable now and carries a {#def#} header, build a
    # validated-field model; otherwise fall back to a permissive placeholder
    # (header is applied lazily on the tag-render path instead).
    from .props_header import build_component_model
    from .renderer import Renderer

    try:
        template_path = Renderer.get_default_renderer()._find_template_for_tag(name)
    except (FileNotFoundError, ValueError):
        template_path = None
    if template_path is not None:
        with open(template_path, encoding="utf-8") as template_file:
            model = build_component_model(name, template_file.read())
        if model is not None:
            return model  # auto-registered via __init_subclass__

    return type(name, (BaseComponent,), {"_pjx_template": name, "_pjx_classless": True})
