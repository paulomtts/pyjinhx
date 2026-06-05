import hashlib
import logging
from typing import Any, ClassVar, Optional

from markupsafe import Markup
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .registry import Registry
from .renderer import Renderer, RenderSession

logger = logging.getLogger("pyjinhx")
logger.setLevel(logging.WARNING)


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

    id: str = Field(..., description="The unique ID for this component.")
    js: list[str] = Field(
        default_factory=list,
        description="List of paths to extra JavaScript files to include.",
    )
    css: list[str] = Field(
        default_factory=list,
        description="List of paths to extra CSS files to include.",
    )

    # State keys this component derives from. Declaring this plus a load()
    # classmethod makes the component reactive (eligible for dependency-aware
    # OOB swaps via oob_swaps()).
    depends_on: ClassVar[set[str]] = set()

    @field_validator("id", mode="before")
    def validate_id(cls, v):
        if not v:
            raise ValueError("ID is required")
        return str(v)

    def __init_subclass__(cls, **kwargs):
        """Register the component class and configure its reactivity at definition time."""
        super().__init_subclass__(**kwargs)
        Registry.register_class(cls)
        cls._configure_reactivity()

    @classmethod
    def _configure_reactivity(cls) -> None:
        """
        Detect whether this subclass is reactive and normalize its dependencies.

        A component is reactive iff it defines a ``load()`` classmethod. The
        derived flags are stored as plain class attributes (not Pydantic fields)
        so they are inherited by further subclasses and never validated.
        """
        has_load = callable(getattr(cls, "load", None))
        declared = set(getattr(cls, "depends_on", None) or ())
        cls._pjx_reactive = has_load
        cls._pjx_depends_on = frozenset(declared)

        if has_load and not declared:
            logger.warning(
                "%s defines load() but no depends_on; it will never match a "
                "dirtied key and is effectively inert.",
                cls.__name__,
            )
        if declared and not has_load:
            logger.warning(
                "%s declares depends_on=%s but no load(); it cannot be reloaded "
                "for reactive OOB swaps.",
                cls.__name__,
                declared,
            )

    def state_hash(self) -> str:
        """
        Return a stable content hash of this component's state.

        Used to gate reactive OOB swaps so a region whose value did not change is
        not re-sent. The default hashes ``model_dump_json()``; override for custom
        hashing. In the always-swap baseline (step 1) this value is stamped onto
        the root element and reported by the client, but not yet used for gating.
        """
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()[:16]

    def __init__(self, **kwargs):
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

    def _update_context_(
        self,
        context: dict[str, Any],
        field_name: str,
        field_value: Any,
        *,
        renderer: Renderer,
        session: RenderSession,
    ) -> dict[str, Any]:
        """
        Updates the context with rendered components by their ID.
        """
        if isinstance(field_value, BaseComponent):
            context[field_name] = NestedComponentWrapper(
                html=field_value._render(
                    base_context=context,
                    _renderer=renderer,
                    _session=session,
                ),
                props=field_value,
            )
        elif isinstance(field_value, list):
            processed_list = []
            for item in field_value:
                if isinstance(item, BaseComponent):
                    processed_list.append(
                        NestedComponentWrapper(
                            html=item._render(
                                base_context=context,
                                _renderer=renderer,
                                _session=session,
                            ),
                            props=item,
                        )
                    )
                else:
                    processed_list.append(item)
            if processed_list:
                context[field_name] = processed_list
        elif isinstance(field_value, dict):
            processed_dict = {}
            for key, value in field_value.items():
                if isinstance(value, BaseComponent):
                    processed_dict[key] = NestedComponentWrapper(
                        html=value._render(
                            base_context=context,
                            _renderer=renderer,
                            _session=session,
                        ),
                        props=value,
                    )
                else:
                    processed_dict[key] = value
            if processed_dict:
                context[field_name] = processed_dict
        return context

    def _render(
        self,
        source: str | None = None,
        base_context: dict[str, Any] | None = None,
        *,
        _renderer: Renderer | None = None,
        _session: RenderSession | None = None,
        _template_path: str | None = None,
    ) -> Markup:
        renderer = _renderer or Renderer.get_default_renderer()

        is_root = base_context is None and _session is None
        session = _session or renderer.new_session()

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

        return renderer.render_component_with_context(
            self,
            context=context,
            template_source=source,
            template_path=_template_path,
            session=session,
            is_root=is_root,
            collect_component_js=source is None,
        )

    def render(
        self,
        *,
        dirtied: set[str] | None = None,
        mounted: object | None = None,
    ) -> Markup:
        """
        Render this component to HTML using its associated Jinja template.

        The template is auto-discovered based on the component class name (e.g., `MyButton` looks
        for `my_button.html` or `my_button.jinja`). All component fields are available in the
        template context, and nested components are rendered recursively.

        With no arguments this is a plain render. Passing ``dirtied`` and/or ``mounted``
        opts into dependency-aware reactivity: this component is rendered as the primary
        response, and an out-of-band swap is appended for every other mounted reactive
        region whose ``depends_on`` intersects ``dirtied`` (each rebuilt via its own
        ``load()``). This component's own region is never additionally swapped.

        Args:
            dirtied: State keys the route mutated (e.g. ``{"todos"}``). Enables reactive mode.
            mounted: The client manifest — a request-like object (the ``X-PJX-Mounted``
                header is read off it without importing any web framework), the raw header
                string, an already-parsed list, or ``None``. Enables reactive mode.

        Returns:
            The rendered HTML as a Markup object (safe for direct use in templates).
        """
        if dirtied is None and mounted is None:
            return self._render()

        from .reactive import oob_swaps  # local import to avoid an import cycle

        primary = self._render()
        swaps = oob_swaps(dirtied or set(), mounted, exclude_ids={self.id})
        return primary + swaps
