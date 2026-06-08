import logging
from typing import Any, Optional

from markupsafe import Markup
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .registry import Registry
from .renderer import Renderer
from .assets import RenderSession
from .utils import ReactiveKey, coerce_reactive_keys

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

    @field_validator("id", mode="before")
    def validate_id(cls, v: object) -> str:
        if not v:
            raise ValueError("ID is required")
        return str(v)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register the component class on subclass definition."""
        super().__init_subclass__(**kwargs)
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
        emit_assets: bool = True,
        client: object | None = None,
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

        from .client_backend import resolve_render_client
        from .reactive import parse_loaded_assets

        resolved_client = resolve_render_client(client)
        loaded_assets = (
            parse_loaded_assets(resolved_client)
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

    def render(
        self,
        *,
        dirtied: set[ReactiveKey] | None = None,
        mounted: object | None = None,
        client: object | None = None,
    ) -> Markup:
        """
        Render this component to HTML using its associated Jinja template.

        The template is auto-discovered based on the component class name (e.g., `MyButton` looks
        for `my_button.html` or `my_button.jinja`). All component fields are available in the
        template context, and nested components are rendered recursively.

        With no arguments this is a plain render. Passing ``dirtied`` and/or ``mounted``
        opts into dependency-aware reactivity: this component is rendered as the primary
        response, and an out-of-band swap is appended for every other mounted reactive
        region whose ``reacts_to`` intersects ``dirtied`` (each rebuilt via its own
        ``load()``). This component's own region is never additionally swapped.

        When ``dirtied`` is omitted it defaults to this component's own ``reacts_to``
        (empty for a non-reactive primary); pass ``dirtied`` explicitly — including an
        empty set — to override.

        Args:
            dirtied: State keys the route mutated (e.g. ``{"todos"}``). Defaults to the
                primary's ``reacts_to``. Enables reactive mode.
            mounted: The client manifest — a request-like object, the raw header string,
                a parsed list, or ``None``. When omitted, uses the request-scoped
                ``ClientBackend`` after mutations (see ``Registry.request_scope``).
            client: Request-like object (or raw ``X-PJX-Assets`` JSON) for REFERENCE-mode
                asset dedup on root renders. When omitted, uses the request-scoped
                ``ClientBackend``.

        Returns:
            The rendered HTML as a Markup object (safe for direct use in templates).
        """
        from .client_backend import resolve_render_client, resolve_render_mounted

        resolved_client = resolve_render_client(client)
        resolved_mounted = resolve_render_mounted(mounted, dirtied=dirtied)

        if dirtied is None and resolved_mounted is None:
            return self._render(client=resolved_client)

        from .mutations import (
            mark_reactive_render_consumed,
            resolve_effective_dirtied,
        )
        from .reactive import oob_swaps  # local import to avoid an import cycle
        from .reactive_dev import warn_reactive_render_without_mounted

        own_keys = coerce_reactive_keys(getattr(self, "_pjx_reacts_to", frozenset()))
        warn_reactive_render_without_mounted(
            dirtied=dirtied, mounted=resolved_mounted, own_keys=own_keys
        )

        primary = self._render(emit_assets=False)
        effective_dirtied = resolve_effective_dirtied(
            dirtied=dirtied,
            mounted=resolved_mounted,
            own_keys=own_keys,
        )
        mark_reactive_render_consumed()
        swaps = oob_swaps(effective_dirtied, resolved_mounted, exclude_ids={self.id})
        # Wrap the primary as safe markup before concatenation: _render() returns a
        # plain str (Markup.unescape()), and `str + Markup` would invoke Markup.__radd__
        # and HTML-escape the primary. Markup(primary) + swaps keeps both raw.
        return Markup(primary) + swaps
