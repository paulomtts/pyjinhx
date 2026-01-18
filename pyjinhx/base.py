import logging
from typing import Any, Optional

from markupsafe import Markup
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .registry import Registry
from .renderer import Renderer, RenderSession

logger = logging.getLogger("pyjinhx")
logger.setLevel(logging.WARNING)


class NestedComponentWrapper(BaseModel):
    """
    A wrapper for nested components. Enables access to the component's properties and rendered HTML.
    """

    html: str
    props: Optional["BaseComponent"]

    def __str__(self) -> Markup:
        return self.html


class BaseComponent(BaseModel):
    "Provides functionality for declaring UI components in python."

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="The unique ID for this component.")
    js: list[str] = Field(
        default_factory=list,
        description="List of paths to extra JavaScript files to include.",
    )
    html: list[str] = Field(
        default_factory=list, description="Extra HTML files to add to the component."
    )

    @field_validator("id", mode="before")
    def validate_id(cls, v):
        if not v:
            raise ValueError("ID is required")
        return str(v)

    def __init_subclass__(cls, **kwargs):
        """Automatically register the component class at definition time."""
        super().__init_subclass__(**kwargs)
        Registry.register_class(cls)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Registry.register_instance(self)

    def __html__(self) -> Markup:
        """
        Automatically renders the component when accessed.
        This allows for cleaner template syntax: {{ MyComponent }} instead of {{ MyComponent.render() }}
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
            session=session,
            is_root=is_root,
            collect_component_js=source is None,
        )

    def render(self) -> Markup:
        return self._render()
