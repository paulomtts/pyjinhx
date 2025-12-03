"""
Defines the BaseComponent for all server-side UI components.
This class holds a reference to the Jinja2 template engine.
"""

import inspect
import os
import re
from contextvars import ContextVar
from typing import Any, ClassVar, Optional, Tuple

from jinja2 import Template
from markupsafe import Markup
from pydantic import BaseModel, Field, field_validator

import logging


logger = logging.getLogger("pyjinx")
logger.setLevel(logging.WARNING)

_registry_context: ContextVar[dict[str, "BaseComponent"]] = ContextVar(
    "component_registry", default={}
)


class Registry:
    """
    Registry for all components.
    """

    @classmethod
    def register(cls, component: "BaseComponent") -> None:
        registry = _registry_context.get()
        if component.id in registry:
            logger.warning(f"While registering{component.__class__.__name__}(id={component.id}) found an existing component with the same id. Overwriting...")
        registry[component.id] = component

    @classmethod
    def clear(cls) -> None:
        _registry_context.set({})

    @classmethod
    def get(cls) -> dict[str, "BaseComponent"]:
        return _registry_context.get()


class BaseComponent(BaseModel):
    "Provides functionality for declaring UI components in python."

    _engine: ClassVar[Optional[Template]] = None

    @classmethod
    def set_engine(cls, templates: Template):
        """
        Sets the Jinja2 templates engine for all components that inherit from this base class.
        This should be called once at application startup.
        """
        cls._engine = templates

    id: str = Field(..., description="The unique ID for this component.")
    js: Optional[str] = Field(
        default=None, description="The JavaScript file for this component."
    )
    html: list[str] = Field(
        default_factory=list, description="Extra HTML files to add to the component."
    )

    @field_validator("id", mode="before")
    def validate_id(cls, v):
        if not v:
            raise ValueError("ID is required")
        return str(v)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Registry.register(self)

    def __html__(self) -> Markup:
        """
        Automatically renders the component when accessed.
        This allows for cleaner template syntax: {{ MyComponent }} instead of {{ MyComponent.render() }}
        """
        return self.render()

    def _get_snake_case_name(self, name: str | None = None) -> str:
        if name is None:
            name = self.__class__.__name__
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    def _get_raw_path(self) -> str:
        return os.path.dirname(inspect.getfile(self.__class__)).replace("\\", "/")

    def _get_relative_path(self, name: str | None = None) -> str:
        raw_path = self._get_raw_path()
        snake_case_name = self._get_snake_case_name(name)
        return f"{raw_path.split('/ui')[1]}/{snake_case_name}.html"

    def _get_js_file_name(self) -> str | None:
        raw_path = self._get_raw_path()
        snake_case_name = self.js if self.js else self._get_snake_case_name()
        js_file_name = snake_case_name.replace("_", "-") + ("" if self.js else ".js")
        if not os.path.exists(f"{raw_path}/{js_file_name}"):
            return None
        return js_file_name

    def _load_template(self, source: str | None = None) -> Tuple[Template, str]:
        if source is None:
            relative_path = self._get_relative_path()
            template: Template = BaseComponent._engine.get_template(relative_path)
            source = template.environment.loader.get_source(
                template.environment, template.name
            )[0]
            return template, source
        else:
            template: Template = BaseComponent._engine.from_string(source)
            return template, source

    def _update_context(
        self,
        template: Template,
        source: str,
        context: dict[str, Any],
        field_value: Any,
    ) -> Tuple[dict[str, Any], Template, str]:
        """
        Updates the context with rendered components by their ID.
        """
        if isinstance(field_value, BaseComponent):
            context[field_value.id] = field_value.render()
        elif isinstance(field_value, list):
            for item in field_value:
                if isinstance(item, BaseComponent):
                    context[item.id] = item.render()
        elif isinstance(field_value, dict) and all(
            isinstance(value, BaseComponent) for value in field_value.values()
        ):
            for item in field_value.values():
                if isinstance(item, BaseComponent):
                    context[item.id] = item.render()
        return context, template, source

    def _add_javascript_file(self, rendered_template: str) -> str:
        js_file_name = self._get_js_file_name()
        if js_file_name:
            raw_path = self._get_raw_path()
            js_path = f"{raw_path}/{js_file_name}"
            if os.path.exists(js_path):
                with open(js_path, "r") as f:
                    js_content = f.read()
                    rendered_template += f'<script>{js_content}</script>'
        return rendered_template

    def render(
        self, source: str | None = None, base_context: dict[str, Any] | None = None
    ) -> Markup:
        """
        Renders the component's template with the given context - including the global components.

        Returns:
            Markup: The rendered component.
        """
        # 1. Load context & template
        context = base_context or self.model_dump()
        template, source = self._load_template(source)

        # 2. Render nested components
        if base_context is None:
            for field_name in type(self).model_fields.keys():
                field_value = getattr(self, field_name)
                context, template, source = self._update_context(
                    template, source, context, field_value
                )

        # 3. Update context with all components & extra HTML templates
        context.update(Registry.get())
        for html_file in self.html:
            with open(html_file, "r") as file:
                html_template = file.read()
                extra_markup = self.render(html_template, context)
                context[html_file] = extra_markup

        # 4. Render template & add JavaScript file
        rendered_template = template.render(context)
        rendered_template = self._add_javascript_file(rendered_template)

        return Markup(rendered_template).unescape()
