from __future__ import annotations

import importlib.util
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from jinja2 import Environment, FileSystemLoader, Template
from jinja2.exceptions import TemplateNotFound
from markupsafe import Markup

from .dataclasses import Tag
from .finder import Finder
from .parser import Parser
from .registry import Registry
from .utils import detect_root_directory, pascal_case_to_kebab_case, pascal_case_to_snake_case

if TYPE_CHECKING:
    from .base import BaseComponent

logger = logging.getLogger("pyjinhx")

_autodiscovered_files: set[str] = set()


def _import_module_from_file(filepath: str) -> None:
    """Import a Python file by path to trigger BaseComponent __init_subclass__ registration."""
    if filepath in _autodiscovered_files:
        return
    _autodiscovered_files.add(filepath)
    try:
        module_name = f"_pyjinhx_autodiscovered_{os.path.splitext(os.path.basename(filepath))[0]}"
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            return
        import sys
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # required for inspect.getfile to resolve the class
        spec.loader.exec_module(module)
    except Exception:
        logger.debug("Failed to autodiscover module at %s", filepath, exc_info=True)


def _try_autodiscover_for_tag(tag_name: str, template_path: str | None) -> None:
    """
    Look for a co-located Python module next to the template and import it so that
    any BaseComponent subclasses defined there are registered without an explicit import.

    Search order: <snake_name>.py → __init__.py → first alphabetical .py in the directory.
    """
    if template_path is None:
        return
    component_dir = os.path.dirname(template_path)
    snake_name = pascal_case_to_snake_case(tag_name)
    for filename in (f"{snake_name}.py", "__init__.py"):
        candidate = os.path.join(component_dir, filename)
        if os.path.exists(candidate):
            _import_module_from_file(candidate)
            return
    try:
        py_files = sorted(f for f in os.listdir(component_dir) if f.endswith(".py"))
        if py_files:
            _import_module_from_file(os.path.join(component_dir, py_files[0]))
    except OSError:
        pass


@dataclass
class RenderSession:
    """
    Per-render state for asset aggregation and deduplication.

    Attributes:
        scripts: Collected JavaScript code snippets to inject.
        collected_js_files: Set of JS file paths already processed (for deduplication).
        styles: Collected CSS code snippets to inject.
        collected_css_files: Set of CSS file paths already processed (for deduplication).
    """

    scripts: list[str] = field(default_factory=list)
    collected_js_files: set[str] = field(default_factory=set)
    styles: list[str] = field(default_factory=list)
    collected_css_files: set[str] = field(default_factory=set)


class Renderer:
    """
    Shared rendering engine used by `BaseComponent` rendering and HTML-like custom-tag rendering.

    This renderer centralizes:
    - Jinja template loading (by component class or explicit file/source)
    - Expansion of PascalCase custom tags inside rendered markup
    - JavaScript collection/deduping and root-level script injection
    - Rendering of HTML-like source strings into component output
    """

    def __init__(
        self,
        environment: Environment,
        *,
        auto_id: bool = True,
        inline_js: bool | None = None,
        inline_css: bool | None = None,
    ) -> None:
        """
        Initialize a Renderer with the given Jinja environment.

        Args:
            environment: The Jinja2 Environment to use for template rendering.
            auto_id: If True (default), generate UUIDs for components without explicit IDs.
            inline_js: If True, JavaScript is collected and injected as <script> tags.
                If False, no scripts are injected. Defaults to the class-level setting.
            inline_css: If True, CSS is collected and injected as <style> tags.
                If False, no styles are injected. Defaults to the class-level setting.
        """
        self._environment = environment
        self._auto_id = auto_id
        self._inline_js = (
            inline_js if inline_js is not None else Renderer._default_inline_js
        )
        self._inline_css = (
            inline_css if inline_css is not None else Renderer._default_inline_css
        )
        self._template_finder_cache: dict[str, Finder] = {}

    _default_environment: ClassVar[Environment | None] = None
    _default_inline_js: ClassVar[bool] = True
    _default_inline_css: ClassVar[bool] = True
    _default_renderers: ClassVar[dict[tuple[int, bool, bool, bool], "Renderer"]] = {}

    @classmethod
    def peek_default_environment(cls) -> Environment | None:
        """
        Return the currently configured default environment without auto-initializing.

        Returns:
            The default Jinja Environment, or None if not yet configured.
        """
        return cls._default_environment

    @classmethod
    def set_default_environment(
        cls, environment: Environment | str | os.PathLike[str] | None
    ) -> None:
        """
        Set or clear the process-wide default Jinja environment.

        Args:
            environment: A Jinja Environment instance, a path to a template directory,
                or None to clear the default and reset to auto-detection.
        """
        if environment is None or isinstance(environment, Environment):
            cls._default_environment = environment
        else:
            cls._default_environment = Environment(
                loader=FileSystemLoader(os.fspath(environment))
            )
        cls._default_renderers.clear()

    @classmethod
    def set_default_inline_js(cls, inline_js: bool) -> None:
        """
        Set the process-wide default for inline JavaScript injection.

        Args:
            inline_js: If True (default), JavaScript is collected and injected as <script> tags.
                If False, no scripts are injected. Use Finder.collect_javascript_files() for static serving.
        """
        cls._default_inline_js = inline_js
        cls._default_renderers.clear()

    @classmethod
    def set_default_inline_css(cls, inline_css: bool) -> None:
        """
        Set the process-wide default for inline CSS injection.

        Args:
            inline_css: If True (default), CSS is collected and injected as <style> tags.
                If False, no styles are injected. Use Finder.collect_css_files() for static serving.
        """
        cls._default_inline_css = inline_css
        cls._default_renderers.clear()

    @classmethod
    def get_default_environment(cls) -> Environment:
        """
        Return the default Jinja environment, auto-initializing if needed.

        If no environment is configured, one is created using auto-detected project root.

        Returns:
            The default Jinja Environment instance.
        """
        if cls._default_environment is None:
            root_dir = detect_root_directory()
            cls._default_environment = Environment(loader=FileSystemLoader(root_dir))
        return cls._default_environment

    @classmethod
    def get_default_renderer(
        cls,
        *,
        auto_id: bool = True,
        inline_js: bool | None = None,
        inline_css: bool | None = None,
    ) -> "Renderer":
        """
        Return a cached default renderer instance.

        Args:
            auto_id: If True, generate UUIDs for components without explicit IDs.
            inline_js: If True, JavaScript is collected and injected as <script> tags.
                If False, no scripts are injected. Defaults to the class-level setting.
            inline_css: If True, CSS is collected and injected as <style> tags.
                If False, no styles are injected. Defaults to the class-level setting.

        Returns:
            A Renderer instance cached by (environment identity, auto_id, inline_js, inline_css).
        """
        environment = cls.get_default_environment()
        effective_inline_js = (
            inline_js if inline_js is not None else cls._default_inline_js
        )
        effective_inline_css = (
            inline_css if inline_css is not None else cls._default_inline_css
        )
        cache_key = (id(environment), auto_id, effective_inline_js, effective_inline_css)
        renderer = cls._default_renderers.get(cache_key)
        if renderer is None:
            renderer = Renderer(
                environment,
                auto_id=auto_id,
                inline_js=effective_inline_js,
                inline_css=effective_inline_css,
            )
            cls._default_renderers[cache_key] = renderer
        return renderer

    @property
    def environment(self) -> Environment:
        """
        The Jinja Environment used by this renderer.

        Returns:
            The Jinja Environment instance.
        """
        return self._environment

    def new_session(self) -> RenderSession:
        """
        Create a new render session for tracking scripts during rendering.

        Returns:
            A fresh RenderSession instance.
        """
        return RenderSession()

    def _get_loader_root(self) -> str:
        loader = self._environment.loader
        if not isinstance(loader, FileSystemLoader):
            raise ValueError("Jinja2 loader must be a FileSystemLoader")
        return Finder.get_loader_root(loader)

    def _get_finder_for_root(self, search_root: str) -> Finder:
        finder = self._template_finder_cache.get(search_root)
        if finder is None:
            finder = Finder(search_root)
            self._template_finder_cache[search_root] = finder
        return finder

    def _load_template_for_component(
        self,
        component: "BaseComponent",
        *,
        template_source: str | None,
        template_path: str | None,
    ) -> Template:
        if template_source is not None:
            return self._environment.from_string(template_source)

        if template_path is not None:
            loader_root = self._get_loader_root()
            relative_path = os.path.relpath(template_path, loader_root)
            return self._environment.get_template(relative_path)

        if type(component).__name__ == "BaseComponent":
            raise FileNotFoundError(
                "No template found. Use a BaseComponent subclass with an adjacent template file, "
                "or use Renderer.render() with PascalCase tags."
            )

        loader_root = self._get_loader_root()
        relative_template_paths = Finder.get_relative_template_paths(
            component_dir=Finder.get_class_directory(type(component)),
            search_root=loader_root,
            component_name=type(component).__name__,
        )

        for relative_template_path in relative_template_paths:
            try:
                return self._environment.get_template(relative_template_path)
            except TemplateNotFound:
                continue

        raise TemplateNotFound(
            ", ".join(relative_template_paths) if relative_template_paths else "unknown"
        )

    def _collect_component_javascript(
        self,
        component: "BaseComponent",
        session: RenderSession,
        *,
        component_dir: str | None = None,
        asset_name: str | None = None,
    ) -> None:
        component_directory = component_dir or Finder.get_class_directory(type(component))
        name = asset_name or pascal_case_to_kebab_case(type(component).__name__)
        javascript_filename = f"{name}.js"
        javascript_path = Finder.find_in_directory(
            component_directory, javascript_filename
        )
        if not javascript_path:
            return

        if javascript_path in session.collected_js_files:
            return

        with open(javascript_path, "r") as file:
            javascript_content = file.read()

        if not javascript_content:
            return

        session.scripts.append(javascript_content)
        session.collected_js_files.add(javascript_path)

    def _collect_extra_javascript(
        self, component: "BaseComponent", session: RenderSession
    ) -> None:
        for javascript_path in component.js:
            normalized_path = os.path.normpath(javascript_path).replace("\\", "/")
            if not os.path.exists(normalized_path):
                logger.warning(
                    "Extra JS file not found: %s (component %s, id=%s)",
                    normalized_path,
                    type(component).__name__,
                    component.id,
                )
                continue
            if normalized_path in session.collected_js_files:
                continue
            with open(normalized_path, "r") as file:
                javascript_content = file.read()
            if not javascript_content:
                continue
            session.scripts.append(javascript_content)
            session.collected_js_files.add(normalized_path)

    def _collect_component_css(
        self,
        component: "BaseComponent",
        session: RenderSession,
        *,
        component_dir: str | None = None,
        asset_name: str | None = None,
    ) -> None:
        component_directory = component_dir or Finder.get_class_directory(type(component))
        name = asset_name or pascal_case_to_kebab_case(type(component).__name__)
        css_filename = f"{name}.css"
        css_path = Finder.find_in_directory(component_directory, css_filename)
        if not css_path:
            return

        if css_path in session.collected_css_files:
            return

        with open(css_path, "r") as file:
            css_content = file.read()

        if not css_content:
            return

        session.styles.append(css_content)
        session.collected_css_files.add(css_path)

    def _collect_extra_css(
        self, component: "BaseComponent", session: RenderSession
    ) -> None:
        for css_path in component.css:
            normalized_path = os.path.normpath(css_path).replace("\\", "/")
            if not os.path.exists(normalized_path):
                logger.warning(
                    "Extra CSS file not found: %s (component %s, id=%s)",
                    normalized_path,
                    type(component).__name__,
                    component.id,
                )
                continue
            if normalized_path in session.collected_css_files:
                continue
            with open(normalized_path, "r") as file:
                css_content = file.read()
            if not css_content:
                continue
            session.styles.append(css_content)
            session.collected_css_files.add(normalized_path)

    def _inject_scripts(self, markup: str, session: RenderSession) -> str:
        if not session.scripts:
            return markup
        script_tags = "\n".join(
            f"<script>{script}</script>" for script in session.scripts
        )
        return f"{markup}\n{script_tags}"

    def _inject_styles(self, markup: str, session: RenderSession) -> str:
        if not session.styles:
            return markup
        style_tags = "\n".join(
            f"<style>{style}</style>" for style in session.styles
        )
        return f"{style_tags}\n{markup}"

    def _find_template_for_tag(self, tag_name: str) -> str:
        loader_root = self._get_loader_root()
        finder = self._get_finder_for_root(loader_root)
        return finder.find_template_for_tag(tag_name)

    def _render_tag_node(
        self,
        node: Tag | str,
        base_context: dict[str, Any],
        session: RenderSession,
    ) -> str:
        if isinstance(node, str):
            return node

        rendered_children = "".join(
            self._render_tag_node(child, base_context=base_context, session=session)
            for child in node.children
        ).strip()

        component_id = node.attrs.get("id")
        if not component_id:
            if not self._auto_id:
                raise ValueError(
                    f'Missing required "id" for <{node.name}> and auto_id=False'
                )
            component_id = f"{node.name.lower()}-{uuid.uuid4().hex}"

        attrs_without_id = {k: v for k, v in node.attrs.items() if k != "id"}

        registry_key = Registry.make_key(node.name, component_id)
        existing_instance = Registry.get_instances().get(registry_key)
        if existing_instance is not None:
            instance_class_name = type(existing_instance).__name__
            if instance_class_name != node.name:
                raise TypeError(
                    f"Tag <{node.name}> references instance '{component_id}' "
                    f"which is of type {instance_class_name}"
                )

            if rendered_children:
                existing_instance.content = rendered_children
            for key, value in attrs_without_id.items():
                setattr(existing_instance, key, value)

            template_path = None
            try:
                template_path = self._find_template_for_tag(node.name)
            except FileNotFoundError:
                pass

            return str(
                existing_instance._render(
                    base_context=base_context,
                    _renderer=self,
                    _session=session,
                    _template_path=template_path,
                )
            )

        template_path: str | None = None
        try:
            template_path = self._find_template_for_tag(node.name)
        except FileNotFoundError:
            pass

        if node.name not in Registry.get_classes():
            _try_autodiscover_for_tag(node.name, template_path)

        component_class = Registry.get_classes().get(node.name)
        if component_class is not None:
            component = component_class(
                id=component_id,
                content=rendered_children,
                **attrs_without_id,
            )
        else:
            if template_path is None:
                raise FileNotFoundError(
                    f"No template found for <{node.name}>. "
                    f"Expected {node.name.lower()}.html or {node.name.lower()}.jinja"
                )
            from .base import BaseComponent  # local import to avoid cycles

            component = BaseComponent(
                id=component_id,
                content=rendered_children,
                **attrs_without_id,
            )
            # Remove from registry - fallback instances should not persist
            # across renders to avoid TypeError on subsequent renders
            Registry.get_instances().pop(Registry.make_key("BaseComponent", component_id), None)

        return str(
            component._render(
                base_context=base_context,
                _renderer=self,
                _session=session,
                _template_path=template_path,
            )
        )

    def _expand_custom_tags(
        self,
        markup: str,
        base_context: dict[str, Any],
        session: RenderSession,
    ) -> str:
        """
        Expand PascalCase custom tags found inside `markup` by parsing and rendering them into HTML.
        """
        if "<" not in markup:
            return markup

        parser = Parser()
        has_custom_tags = False
        for match in re.finditer(r"<\s*([A-Za-z][A-Za-z0-9]*)", markup):
            if parser._is_custom_component(match.group(1)):
                has_custom_tags = True
                break
        if not has_custom_tags:
            return markup

        parser.feed(markup)
        return "".join(
            self._render_tag_node(node, base_context=base_context, session=session)
            for node in parser.root_nodes
        )

    def render_component_with_context(
        self,
        component: "BaseComponent",
        context: dict[str, Any],
        template_source: str | None,
        template_path: str | None,
        session: RenderSession,
        is_root: bool,
        collect_component_js: bool,
    ) -> Markup:
        template = self._load_template_for_component(
            component, template_source=template_source, template_path=template_path
        )

        render_context = dict(context)
        for _instance in Registry.get_instances().values():
            render_context[_instance.id] = _instance

        rendered_markup = template.render(render_context)
        rendered_markup = self._expand_custom_tags(
            rendered_markup, base_context=render_context, session=session
        )

        # For bare BaseComponent fallbacks (no registered class), derive the asset
        # directory and name from the template path rather than the class file location,
        # which would otherwise resolve to the pyjinhx package directory.
        if template_path is not None and type(component).__name__ == "BaseComponent":
            _asset_dir: str | None = os.path.dirname(template_path)
            _asset_name: str | None = os.path.splitext(os.path.basename(template_path))[0].replace("_", "-")
        else:
            _asset_dir = None
            _asset_name = None

        if collect_component_js and self._inline_js:
            self._collect_component_javascript(component, session, component_dir=_asset_dir, asset_name=_asset_name)
        if collect_component_js and self._inline_css:
            self._collect_component_css(component, session, component_dir=_asset_dir, asset_name=_asset_name)

        if is_root:
            if self._inline_css:
                self._collect_extra_css(component, session)
                rendered_markup = self._inject_styles(rendered_markup, session)
            if self._inline_js:
                self._collect_extra_javascript(component, session)
                rendered_markup = self._inject_scripts(rendered_markup, session)

        return Markup(rendered_markup).unescape()

    def render(self, source: str) -> str:
        """
        Render an HTML-like source string, expanding PascalCase component tags into HTML.

        PascalCase tags (e.g., `<MyButton text="OK">`) are matched to registered component
        classes or template files and rendered recursively. Standard HTML is passed through
        unchanged. Associated JavaScript files are collected and injected as a `<script>` block.

        Args:
            source: HTML-like string containing component tags to render.

        Returns:
            The fully rendered HTML string with all components expanded.
        """
        parser = Parser()
        parser.feed(source)

        session = self.new_session()

        rendered_markup = "".join(
            self._render_tag_node(node, base_context={}, session=session)
            for node in parser.root_nodes
        )
        if self._inline_css:
            rendered_markup = self._inject_styles(rendered_markup, session)
        if self._inline_js:
            rendered_markup = self._inject_scripts(rendered_markup, session)
        return rendered_markup.strip()
