from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, ClassVar

from jinja2 import Environment, FileSystemLoader, Template
from jinja2.exceptions import TemplateNotFound
from markupsafe import Markup

from .assets import (
    DEFAULT_RUNTIME_URL as _DEFAULT_RUNTIME_URL,
    AssetMode,
    AssetUrlResolver,
    RenderSession,
    asset_mode_from_inline,
    make_default_asset_url_resolver,
    runtime_asset_path,
)
from .finder import Finder
from .parser import Parser
from .registry import Registry
from .render_assets import (
    collect_component_asset,
    collect_extra_assets,
    inject_assets,
    inject_runtime,
    normalize_asset_path,
)
from .tag_expand import expand_custom_tags, render_tag_node
from ..utils import (
    detect_root_directory,
    stamp_root_attributes,
    tag_name_to_template_filenames,
)

if TYPE_CHECKING:
    from .base import BaseComponent

logger = logging.getLogger("pyjinhx")


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
        js_mode: AssetMode | None = None,
        css_mode: AssetMode | None = None,
    ) -> None:
        """
        Initialize a Renderer with the given Jinja environment.

        Args:
            environment: The Jinja2 Environment to use for template rendering.
            auto_id: If True (default), generate UUIDs for components without explicit IDs.
            inline_js: Deprecated bool shim; maps to INLINE or NONE for JavaScript.
            inline_css: Deprecated bool shim; maps to INLINE or NONE for CSS.
            js_mode: How JavaScript assets are delivered. Defaults to the class-level setting.
            css_mode: How CSS assets are delivered. Defaults to the class-level setting.
        """
        self._environment = environment
        self._auto_id = auto_id
        if js_mode is not None:
            self._js_mode = js_mode
        elif inline_js is not None:
            self._js_mode = asset_mode_from_inline(inline_js)
        else:
            self._js_mode = Renderer._default_js_mode
        if css_mode is not None:
            self._css_mode = css_mode
        elif inline_css is not None:
            self._css_mode = asset_mode_from_inline(inline_css)
        else:
            self._css_mode = Renderer._default_css_mode
        self._template_finder_cache: dict[str, Finder] = {}

    _default_environment: ClassVar[Environment | None] = None
    _default_js_mode: ClassVar[AssetMode] = AssetMode.INLINE
    _default_css_mode: ClassVar[AssetMode] = AssetMode.INLINE
    _default_runtime_url: ClassVar[str] = _DEFAULT_RUNTIME_URL
    _asset_url_resolver: ClassVar[AssetUrlResolver | None] = None
    _default_asset_dedup: ClassVar[bool] = False
    _default_renderers: ClassVar[
        dict[tuple[int, bool, AssetMode, AssetMode, int], "Renderer"]
    ] = {}

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
    def set_default_js_mode(cls, mode: AssetMode) -> None:
        """Set the process-wide default JavaScript asset delivery mode."""
        cls._default_js_mode = mode
        cls._default_renderers.clear()

    @classmethod
    def set_default_css_mode(cls, mode: AssetMode) -> None:
        """Set the process-wide default CSS asset delivery mode."""
        cls._default_css_mode = mode
        cls._default_renderers.clear()

    @classmethod
    def set_default_inline_js(cls, inline_js: bool) -> None:
        """
        Set the process-wide default for inline JavaScript injection.

        Args:
            inline_js: If True (default), JavaScript is collected and injected as <script> tags.
                If False, no scripts are injected. Use AssetMode.REFERENCE for URL tags.
        """
        cls.set_default_js_mode(asset_mode_from_inline(inline_js))

    @classmethod
    def set_default_inline_css(cls, inline_css: bool) -> None:
        """
        Set the process-wide default for inline CSS injection.

        Args:
            inline_css: If True (default), CSS is collected and injected as <style> tags.
                If False, no styles are injected. Use AssetMode.REFERENCE for URL tags.
        """
        cls.set_default_css_mode(asset_mode_from_inline(inline_css))

    @classmethod
    def set_default_runtime_url(cls, url: str) -> None:
        """Set the public URL used for the pyjinhx client runtime in REFERENCE mode."""
        cls._default_runtime_url = url
        cls._default_renderers.clear()

    @classmethod
    def set_asset_url_resolver(cls, resolver: AssetUrlResolver | None) -> None:
        """Set the callable that maps absolute asset paths to public URLs."""
        cls._asset_url_resolver = resolver
        cls._default_renderers.clear()

    @classmethod
    def set_default_asset_dedup(cls, enabled: bool) -> None:
        """Enable filtering of REFERENCE assets already reported by the client."""
        cls._default_asset_dedup = enabled

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
        js_mode: AssetMode | None = None,
        css_mode: AssetMode | None = None,
    ) -> "Renderer":
        """
        Return a cached default renderer instance.

        Args:
            auto_id: If True, generate UUIDs for components without explicit IDs.
            inline_js: Deprecated bool shim for JavaScript delivery mode.
            inline_css: Deprecated bool shim for CSS delivery mode.
            js_mode: JavaScript asset delivery mode. Defaults to the class-level setting.
            css_mode: CSS asset delivery mode. Defaults to the class-level setting.

        Returns:
            A Renderer instance cached by environment identity and asset settings.
        """
        environment = cls.get_default_environment()
        effective_js_mode = (
            js_mode
            if js_mode is not None
            else (
                asset_mode_from_inline(inline_js)
                if inline_js is not None
                else cls._default_js_mode
            )
        )
        effective_css_mode = (
            css_mode
            if css_mode is not None
            else (
                asset_mode_from_inline(inline_css)
                if inline_css is not None
                else cls._default_css_mode
            )
        )
        resolver_id = id(cls._asset_url_resolver)
        cache_key = (
            id(environment),
            auto_id,
            effective_js_mode,
            effective_css_mode,
            resolver_id,
        )
        renderer = cls._default_renderers.get(cache_key)
        if renderer is None:
            renderer = Renderer(
                environment,
                auto_id=auto_id,
                js_mode=effective_js_mode,
                css_mode=effective_css_mode,
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

    def _resolve_asset_url(self, path: str) -> str:
        normalized_path = normalize_asset_path(path)
        if normalized_path == normalize_asset_path(runtime_asset_path()):
            return Renderer._default_runtime_url
        resolver = Renderer._asset_url_resolver
        if resolver is not None:
            return resolver(normalized_path)
        root = self._get_loader_root()
        return make_default_asset_url_resolver(root)(normalized_path)

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

        if type(component).__module__.startswith("pyjinhx.builtins"):
            component_dir = Finder.get_class_directory(type(component))
            for filename in tag_name_to_template_filenames(type(component).__name__):
                candidate_path = os.path.join(component_dir, filename)
                if os.path.isfile(candidate_path):
                    with open(candidate_path, encoding="utf-8") as template_file:
                        return self._environment.from_string(template_file.read())

        raise TemplateNotFound(
            ", ".join(relative_template_paths) if relative_template_paths else "unknown"
        )

    def _find_template_for_tag(self, tag_name: str) -> str:
        loader_root = self._get_loader_root()
        finder = self._get_finder_for_root(loader_root)
        return finder.find_template_for_tag(tag_name)

    def render_component_with_context(
        self,
        component: "BaseComponent",
        context: dict[str, Any],
        template_source: str | None,
        template_path: str | None,
        session: RenderSession,
        is_root: bool,
        collect_component_js: bool,
        *,
        emit_assets: bool = True,
        loaded_assets: frozenset[str] = frozenset(),
        client: object | None = None,
    ) -> Markup:
        template = self._load_template_for_component(
            component, template_source=template_source, template_path=template_path
        )

        render_context = dict(context)
        _key = getattr(component, "_pjx_key", None)
        if _key is not None:
            render_context["key"] = _key
        for _instance in Registry.get_instances().values():
            render_context[_instance.id] = _instance

        rendered_markup = template.render(render_context)
        rendered_markup = expand_custom_tags(
            self,
            rendered_markup,
            base_context=render_context,
            session=session,
            emit_assets=emit_assets,
        )

        if getattr(type(component), "_pjx_reactive", False):
            _attrs = {
                "data-pjx-id": component.id,
                "data-pjx-type": type(component).__name__,
                "data-pjx-hash": component.state_hash(),
            }
            _key = getattr(component, "_pjx_key", None)
            if _key is not None:
                _attrs["data-pjx-key"] = str(_key)
            rendered_markup = stamp_root_attributes(rendered_markup, _attrs)

        if not emit_assets:
            return Markup(rendered_markup).unescape()

        if template_path is not None and type(component).__name__ == "BaseComponent":
            _asset_dir: str | None = os.path.dirname(template_path)
            _asset_name: str | None = os.path.splitext(os.path.basename(template_path))[
                0
            ].replace("_", "-")
        else:
            _asset_dir = None
            _asset_name = None

        if collect_component_js:
            collect_component_asset(
                component,
                session,
                "js",
                js_mode=self._js_mode,
                css_mode=self._css_mode,
                component_dir=_asset_dir,
                asset_name=_asset_name,
            )
            collect_component_asset(
                component,
                session,
                "css",
                js_mode=self._js_mode,
                css_mode=self._css_mode,
                component_dir=_asset_dir,
                asset_name=_asset_name,
            )

        if is_root:
            if self._css_mode != AssetMode.NONE:
                collect_extra_assets(
                    component,
                    session,
                    "css",
                    js_mode=self._js_mode,
                    css_mode=self._css_mode,
                )
            if self._js_mode != AssetMode.NONE:
                inject_runtime(session, js_mode=self._js_mode, client=client)
                collect_extra_assets(
                    component,
                    session,
                    "js",
                    js_mode=self._js_mode,
                    css_mode=self._css_mode,
                )
            if self._css_mode != AssetMode.NONE or self._js_mode != AssetMode.NONE:
                rendered_markup = inject_assets(
                    rendered_markup,
                    session,
                    js_mode=self._js_mode,
                    css_mode=self._css_mode,
                    resolve_url=self._resolve_asset_url,
                    loaded_assets=loaded_assets,
                    dedup_enabled=Renderer._default_asset_dedup,
                )

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
        parser.close()

        session = self.new_session()

        rendered_markup = "".join(
            render_tag_node(
                self,
                node,
                base_context={},
                session=session,
                emit_assets=True,
            )
            for node in parser.root_nodes
        )
        if self._css_mode != AssetMode.NONE or self._js_mode != AssetMode.NONE:
            rendered_markup = inject_assets(
                rendered_markup,
                session,
                js_mode=self._js_mode,
                css_mode=self._css_mode,
                resolve_url=self._resolve_asset_url,
                dedup_enabled=Renderer._default_asset_dedup,
            )
        return rendered_markup.strip()
