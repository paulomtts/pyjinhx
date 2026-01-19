from __future__ import annotations

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
from .utils import detect_root_directory, pascal_case_to_kebab_case

if TYPE_CHECKING:
    from .base import BaseComponent


@dataclass
class RenderSession:
    """Per-root-render state for script aggregation and deduplication."""

    scripts: list[str] = field(default_factory=list)
    collected_js_files: set[str] = field(default_factory=set)


class Renderer:
    """
    Shared rendering engine used by `BaseComponent` rendering and HTML-like custom-tag rendering.

    This renderer centralizes:
    - Jinja template loading (by component class or explicit file/source)
    - Expansion of PascalCase custom tags inside rendered markup
    - JavaScript collection/deduping and root-level script injection
    - Rendering of HTML-like source strings into component output
    """

    def __init__(self, environment: Environment, *, auto_id: bool = True) -> None:
        self._environment = environment
        self._auto_id = auto_id
        self._template_finder_cache: dict[str, Finder] = {}

    _default_environment: ClassVar[Environment | None] = None
    _default_renderers: ClassVar[dict[tuple[int, bool], "Renderer"]] = {}

    @classmethod
    def peek_default_environment(cls) -> Environment | None:
        """Return the currently configured default environment, without auto-initializing it."""
        return cls._default_environment

    @classmethod
    def set_default_environment(
        cls, environment: Environment | str | os.PathLike[str] | None
    ) -> None:
        """
        Set or clear the process-wide default Jinja environment used by `get_default_renderer()`.

        Passing None resets auto-detection behavior.

        Args:
            environment: The Jinja environment to use, or a path to a directory containing templates.
                        If a path, a new `Environment(loader=FileSystemLoader(...))` is created.
                        If None, the default environment is cleared.

        Returns:
            The created `Environment` instance, or None if the environment was cleared.
        """
        if environment is None or isinstance(environment, Environment):
            cls._default_environment = environment
        else:
            cls._default_environment = Environment(
                loader=FileSystemLoader(os.fspath(environment))
            )
        cls._default_renderers.clear()

    @classmethod
    def get_default_environment(cls) -> Environment:
        """Return the default environment, initializing it via root auto-detection if needed."""
        if cls._default_environment is None:
            root_dir = detect_root_directory()
            cls._default_environment = Environment(loader=FileSystemLoader(root_dir))
        return cls._default_environment

    @classmethod
    def get_default_renderer(cls, *, auto_id: bool = True) -> "Renderer":
        """
        Return a cached default renderer instance.

        The renderer is cached by (environment identity, auto_id).
        """
        environment = cls.get_default_environment()
        cache_key = (id(environment), auto_id)
        renderer = cls._default_renderers.get(cache_key)
        if renderer is None:
            renderer = Renderer(environment, auto_id=auto_id)
            cls._default_renderers[cache_key] = renderer
        return renderer

    @property
    def environment(self) -> Environment:
        """Return the Jinja Environment used by this renderer."""
        return self._environment

    def new_session(self) -> RenderSession:
        """Create a new root render session."""
        return RenderSession()

    def _get_loader_root(self) -> str:
        loader = self._environment.loader
        if not isinstance(loader, FileSystemLoader):
            raise ValueError("Jinja2 loader must be a FileSystemLoader")
        return Finder.get_loader_root(loader)

    def _to_template_name(self, path: str) -> str:
        loader_root = self._get_loader_root()

        if os.path.isabs(path):
            normalized_loader_root = os.path.normpath(loader_root)
            normalized_path = os.path.normpath(path)
            if (
                os.path.commonpath([normalized_loader_root, normalized_path])
                != normalized_loader_root
            ):
                raise TemplateNotFound(path)
            relative_path = os.path.relpath(normalized_path, normalized_loader_root)
        else:
            relative_path = path

        return os.path.normpath(relative_path).replace("\\", "/")

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
    ) -> Template:
        if template_source is not None:
            return self._environment.from_string(template_source)

        if type(component).__name__ == "BaseComponent":
            if not component.html:
                raise FileNotFoundError(
                    "No template files found. BaseComponent requires 'html' property to be set with template file paths."
                )

            template_names = [self._to_template_name(path) for path in component.html]
            includes: list[str] = []
            for template_name in template_names[:-1]:
                includes.append(f"{{% include {template_name!r} %}}\n")
            includes.append(f"{{% include {template_names[-1]!r} %}}\n\n")
            combined_template_source = "".join(includes)
            return self._environment.from_string(combined_template_source)

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

        if component.html and len(component.html) == 1:
            template_name = self._to_template_name(component.html[0])
            return self._environment.get_template(template_name)

        raise TemplateNotFound(
            ", ".join(relative_template_paths) if relative_template_paths else "unknown"
        )

    def _collect_component_javascript(
        self, component: "BaseComponent", session: RenderSession
    ) -> None:
        component_directory = Finder.get_class_directory(type(component))
        javascript_filename = (
            f"{pascal_case_to_kebab_case(type(component).__name__)}.js"
        )
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
                continue
            if normalized_path in session.collected_js_files:
                continue
            with open(normalized_path, "r") as file:
                javascript_content = file.read()
            if not javascript_content:
                continue
            session.scripts.append(javascript_content)
            session.collected_js_files.add(normalized_path)

    def _inject_scripts(self, markup: str, session: RenderSession) -> str:
        if not session.scripts:
            return markup
        combined_script = "\n".join(session.scripts)
        return f"<script>{combined_script}</script>\n{markup}"

    def _inject_extra_html_context(
        self,
        component: "BaseComponent",
        render_context: dict[str, Any],
        session: RenderSession,
    ) -> dict[str, Any]:
        for html_file in component.html:
            template_name = self._to_template_name(html_file)
            try:
                template = self._environment.get_template(template_name)
            except TemplateNotFound as exc:
                raise FileNotFoundError(str(exc)) from exc

            extra_markup = template.render(render_context)
            extra_markup = self._expand_custom_tags(
                extra_markup, base_context=render_context, session=session
            )

            html_key = html_file.split("/")[-1].split(".")[0]

            from .base import NestedComponentWrapper

            render_context[html_key] = NestedComponentWrapper(
                html=str(extra_markup),
                props=None,
            )

        return render_context

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

        component_class = Registry.get_classes().get(node.name)
        if component_class is not None:
            component_kwargs: dict[str, Any] = {
                "id": component_id,
                "content": rendered_children,
                **attrs_without_id,
            }
            try:
                component_kwargs["html"] = [self._find_template_for_tag(node.name)]
            except FileNotFoundError:
                pass
            component = component_class(**component_kwargs)
        else:
            template_path = self._find_template_for_tag(node.name)
            from .base import BaseComponent  # local import to avoid cycles

            component = BaseComponent(
                id=component_id,
                html=[template_path],
                content=rendered_children,
                **attrs_without_id,
            )

        return str(
            component._render(
                base_context=base_context,
                _renderer=self,
                _session=session,
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
        session: RenderSession,
        is_root: bool,
        collect_component_js: bool,
    ) -> Markup:
        template = self._load_template_for_component(
            component, template_source=template_source
        )

        render_context = dict(context)
        render_context.update(Registry.get_instances())
        if is_root:
            render_context = self._inject_extra_html_context(
                component, render_context, session=session
            )

        rendered_markup = template.render(render_context)
        rendered_markup = self._expand_custom_tags(
            rendered_markup, base_context=render_context, session=session
        )

        if collect_component_js:
            self._collect_component_javascript(component, session)

        if is_root:
            self._collect_extra_javascript(component, session)
            rendered_markup = self._inject_scripts(rendered_markup, session)

        return Markup(rendered_markup).unescape()

    def render(self, source: str) -> str:
        """
        Render an HTML-like source string containing PascalCase component tags.
        """
        parser = Parser()
        parser.feed(source)

        session = self.new_session()

        rendered_markup = "".join(
            self._render_tag_node(node, base_context={}, session=session)
            for node in parser.root_nodes
        )
        rendered_markup = self._inject_scripts(rendered_markup, session)
        return rendered_markup.strip()
