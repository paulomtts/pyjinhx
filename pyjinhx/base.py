import inspect
import logging
import os
import re
from contextvars import ContextVar
from typing import Any, ClassVar, Optional, List, Type

from jinja2 import Environment, FileSystemLoader, Template
from markupsafe import Markup
from pydantic import BaseModel, Field, field_validator, ConfigDict

logger = logging.getLogger("pyjinhx")
logger.setLevel(logging.WARNING)

_registry_context: ContextVar[dict[str, "BaseComponent"]] = ContextVar(
    "component_registry", default={}
)

_scripts_context: ContextVar[list[str]] = ContextVar(
    "scripts_collection", default=[]
)

_collected_js_context: ContextVar[set[str]] = ContextVar(
    "collected_js_files", default=set()
)


class Registry:
    """
    Registry for all components.
    """
    _class_registry: ClassVar[dict[str, Type["BaseComponent"]]] = {}

    @classmethod
    def register_class(cls, component_class: type["BaseComponent"]) -> None:
        """Register a component class by its name."""
        class_name = component_class.__name__
        if class_name in cls._class_registry:
            logger.warning(
                f"Component class {class_name} is already registered. Overwriting..."
            )
        cls._class_registry[class_name] = component_class

    @classmethod
    def get_classes(cls) -> dict[str, type["BaseComponent"]]:
        """Get all registered component classes."""
        return cls._class_registry

    @classmethod
    def register(cls, component: "BaseComponent") -> None:
        registry = _registry_context.get()
        if component.id in registry:
            logger.warning(
                f"While registering{component.__class__.__name__}(id={component.id}) found an existing component with the same id. Overwriting..."
            )
        registry[component.id] = component

    @classmethod
    def clear(cls) -> None:
        _registry_context.set({})

    @classmethod
    def get(cls) -> dict[str, "BaseComponent"]:
        return _registry_context.get()

class Object(BaseModel):
    """
    A wrapper for nested components. Enables access to the component's properties and rendered HTML.
    """
    html: str
    props: Optional["BaseComponent"]

    def __str__(self) -> Markup:
        return self.html



class BaseComponent(BaseModel):
    "Provides functionality for declaring UI components in python."

    model_config = ConfigDict(extra='allow')
    _engine: ClassVar[Optional[Environment]] = None

    @classmethod
    def set_engine(cls, environment: Environment):
        """
        Sets the Jinja2 environment for all components that inherit from this base class.
        This should be called once at application startup if the root directory auto-detection fails.
        """
        cls._engine = environment

    @classmethod
    def _detect_root_directory(cls) -> str:
        """
        Attempts to detect a reasonable root directory for the template loader.
        Looks for common project markers or uses the current working directory.
        """
        current_dir = os.getcwd()

        project_markers = ["pyproject.toml", "main.py", "README.md", ".git"]

        search_dir = current_dir
        while search_dir != os.path.dirname(search_dir):
            for marker in project_markers:
                if os.path.exists(os.path.join(search_dir, marker)):
                    return search_dir
            search_dir = os.path.dirname(search_dir)

        return current_dir

    id: str = Field(..., description="The unique ID for this component.")
    js: List[str] = Field(
        default_factory=list, description="List of paths to extra JavaScript files to include."
    )
    html: list[str] = Field(
        default_factory=list, description="Extra HTML files to add to the component."
    )

    @classmethod
    def _ensure_engine_(cls) -> Environment:
        """
        Ensures the Jinja2 environment is initialized.
        Creates it automatically if not already set.
        """
        if cls._engine is None:
            root_dir = cls._detect_root_directory()
            cls._engine = Environment(loader=FileSystemLoader(root_dir))
        return cls._engine

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
        Registry.register(self)

    def __html__(self) -> Markup:
        """
        Automatically renders the component when accessed.
        This allows for cleaner template syntax: {{ MyComponent }} instead of {{ MyComponent.render() }}
        """
        return self._render()

    def _get_snake_case_name(self, name: str | None = None) -> str:
        if name is None:
            name = self.__class__.__name__
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    def _get_raw_path(self) -> str:
        return os.path.dirname(inspect.getfile(self.__class__)).replace("\\", "/")

    def _get_relative_path(self, name: str | None = None) -> str:
        raw_path = self._get_raw_path()
        snake_case_name = self._get_snake_case_name(name)

        engine = BaseComponent._ensure_engine_()
        loader = engine.loader
        if not isinstance(loader, FileSystemLoader):
            raise ValueError("Jinja2 loader must be a FileSystemLoader")

        search_path = (
            loader.searchpath[0]
            if isinstance(loader.searchpath, list)
            else loader.searchpath
        )
        relative_dir = os.path.relpath(raw_path, search_path).replace("\\", "/")

        return f"{relative_dir}/{snake_case_name}.html"

    def _collect_extra_html_files_(self) -> str:
        combined_html = ""
        engine = BaseComponent._ensure_engine_()
        loader = engine.loader
        if not isinstance(loader, FileSystemLoader):
            raise ValueError("Jinja2 loader must be a FileSystemLoader")
        
        search_path = (
            loader.searchpath[0]
            if isinstance(loader.searchpath, list)
            else loader.searchpath
        )
        
        for html_file in self.html:
            if os.path.isabs(html_file):
                file_path = html_file
            else:
                file_path = os.path.join(search_path, html_file)
            
            with open(file_path, "r") as file:
                combined_html += file.read() + "\n"

        return combined_html

    def _load_template(self, source: str | None = None) -> Template:
        engine = BaseComponent._ensure_engine_()
        if source is None and type(self) is not BaseComponent:
            relative_path = self._get_relative_path()
            return engine.get_template(relative_path)
        elif source is None and type(self) is BaseComponent:
            if not self.html:
                raise FileNotFoundError("No template files found. BaseComponent requires 'html' property to be set with template file paths.")
            html_content = self._collect_extra_html_files_()
            return engine.from_string(html_content)
        else:
            return engine.from_string(source)

    def _update_context_(
        self,
        context: dict[str, Any],
        field_name: str,
        field_value: Any,
    ) -> dict[str, Any]:
        """
        Updates the context with rendered components by their ID.
        """
        if isinstance(field_value, BaseComponent):
            context[field_name] = Object(html=field_value._render(base_context=context), props=field_value)
        elif isinstance(field_value, list):
            processed_list = []
            for item in field_value:
                if isinstance(item, BaseComponent):
                    processed_list.append(Object(html=item._render(base_context=context), props=item))
                else:
                    processed_list.append(item)
            if processed_list:
                context[field_name] = processed_list
        elif isinstance(field_value, dict):
            processed_dict = {}
            for key, value in field_value.items():
                if isinstance(value, BaseComponent):
                    processed_dict[key] = Object(html=value._render(base_context=context), props=value)
                else:
                    processed_dict[key] = value
            if processed_dict:
                context[field_name] = processed_dict
        return context

    def _get_javascript_file_name(self) -> str | None:
        raw_path = self._get_raw_path()
        snake_case_name = self._get_snake_case_name()
        js_file_name = snake_case_name.replace("_", "-") + ".js"
        if not os.path.exists(f"{raw_path}/{js_file_name}"):
            return None
        return js_file_name

    def _get_javascript_path(self) -> str | None:
        js_file_name = self._get_javascript_file_name()
        if js_file_name:
            raw_path = self._get_raw_path()
            js_path = f"{raw_path}/{js_file_name}"
            if os.path.exists(js_path):
                return js_path
        return None

    def _get_javascript_content(self) -> str | None:
        js_path = self._get_javascript_path()
        if js_path:
            with open(js_path, "r") as f:
                return f.read()
        return None

    def _collect_javascript_if_needed_(self) -> None:
        js_path = self._get_javascript_path()
        if js_path:
            collected_files = _collected_js_context.get()
            if js_path not in collected_files:
                js_content = self._get_javascript_content()
                if js_content:
                    scripts = _scripts_context.get()
                    scripts.append(js_content)
                    _scripts_context.set(scripts)
                    collected_files.add(js_path)
                    _collected_js_context.set(collected_files)

    def _collect_extra_javascript_files_(self) -> None:
        collected_files = _collected_js_context.get()
        for js_path in self.js:
            normalized_path = os.path.normpath(js_path).replace("\\", "/")
            if normalized_path not in collected_files:
                if os.path.exists(normalized_path):
                    with open(normalized_path, "r") as f:
                        js_content = f.read()
                        scripts = _scripts_context.get()
                        scripts.append(js_content)
                        _scripts_context.set(scripts)
                        collected_files.add(normalized_path)
                        _collected_js_context.set(collected_files)

    def _process_extra_html_files_(self, context: dict[str, Any]) -> dict[str, Any]:
        engine = BaseComponent._ensure_engine_()
        loader = engine.loader
        if not isinstance(loader, FileSystemLoader):
            raise ValueError("Jinja2 loader must be a FileSystemLoader")
        
        search_path = (
            loader.searchpath[0]
            if isinstance(loader.searchpath, list)
            else loader.searchpath
        )
        
        for html_file in self.html:
            if os.path.isabs(html_file):
                file_path = html_file
            else:
                file_path = os.path.join(search_path, html_file)
            
            with open(file_path, "r") as file:
                html_template = file.read()
                extra_markup = self._render(html_template, context)
                html_key = html_file.split("/")[-1].split(".")[0]
                context[html_key] = Object(html=extra_markup, props=None)
        return context

    def _render(
        self, source: str | None = None, base_context: dict[str, Any] | None = None
    ) -> Markup:
        """
        Renders the component's template with the given context - including the global components.

        Returns:
            Markup: The rendered component.
        """
        # 0. Setup
        is_root = base_context is None
        if is_root:
            _scripts_context.set([])
            _collected_js_context.set(set())

        # 1. Load context & template
        if base_context is None:
            context = self.model_dump()
        else:
            context = {**base_context, **self.model_dump()}
        template = self._load_template(source)

        # 2. Render nested components
        for field_name in type(self).model_fields.keys():
            field_value = getattr(self, field_name)
            context = self._update_context_(context, field_name, field_value)

        # 3. Update context with all components & extra HTML templates
        context.update(Registry.get())
        if is_root:
            context = self._process_extra_html_files_(context)

        # 4. Render template
        rendered_template = template.render(context)

        # 5. Collect JavaScript from this component (only for component's own template, not extra HTML)
        if source is None:
            self._collect_javascript_if_needed_()

        # 6. Collect extra JavaScript files at root level
        if is_root:
            self._collect_extra_javascript_files_()

        # 7. Append all collected scripts at root level
        if is_root:
            scripts = _scripts_context.get()
            if scripts:
                combined_script = "\n".join(scripts)
                rendered_template = f"<script>{combined_script}</script>\n{rendered_template}"

        return Markup(rendered_template).unescape()

    def render(self) -> Markup:
        return self._render()