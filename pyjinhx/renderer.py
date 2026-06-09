from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, ClassVar

from jinja2 import Environment, FileSystemLoader, Template
from jinja2.exceptions import TemplateNotFound
from markupsafe import Markup

from .assets import (
    DEFAULT_RUNTIME_URL as _DEFAULT_RUNTIME_URL,
    AssetMode,
    AssetPolicy,
    AssetUrlResolver,
    RenderSession,
    apply_component_render_assets,
    inject_assets,
    make_default_asset_url_resolver,
    normalize_asset_path,
    runtime_asset_path,
)
from .finder import Finder
from .registry import Registry
from .tags import Parser, expand_custom_tags, render_tag_node
from .utils import detect_root_directory, stamp_root_attributes, tag_name_to_template_filenames

if TYPE_CHECKING:
    from .base import BaseComponent


def get_loader_root(environment: Environment) -> str:
    loader = environment.loader
    if not isinstance(loader, FileSystemLoader):
        raise ValueError("Jinja2 loader must be a FileSystemLoader")
    return Finder.get_loader_root(loader)


def get_finder_for_root(renderer: Renderer, search_root: str) -> Finder:
    finder = renderer._template_finder_cache.get(search_root)
    if finder is None:
        finder = Finder(search_root)
        renderer._template_finder_cache[search_root] = finder
    return finder


def load_template_for_component(
    renderer: Renderer,
    component: BaseComponent,
    *,
    template_source: str | None,
    template_path: str | None,
) -> Template:
    environment = renderer.environment
    if template_source is not None:
        return environment.from_string(template_source)

    if template_path is not None:
        loader_root = get_loader_root(environment)
        relative_path = os.path.relpath(template_path, loader_root)
        return environment.get_template(relative_path)

    if type(component).__name__ == "BaseComponent":
        raise FileNotFoundError(
            "No template found. Use a BaseComponent subclass with an adjacent template file, "
            "or use Renderer.render() with PascalCase tags."
        )

    loader_root = get_loader_root(environment)
    relative_template_paths = Finder.get_relative_template_paths(
        component_dir=Finder.get_class_directory(type(component)),
        search_root=loader_root,
        component_name=type(component).__name__,
    )

    for relative_template_path in relative_template_paths:
        try:
            return environment.get_template(relative_template_path)
        except TemplateNotFound:
            continue

    if type(component).__module__.startswith("pyjinhx.builtins"):
        component_dir = Finder.get_class_directory(type(component))
        for filename in tag_name_to_template_filenames(type(component).__name__):
            candidate_path = os.path.join(component_dir, filename)
            if os.path.isfile(candidate_path):
                with open(candidate_path, encoding="utf-8") as template_file:
                    return environment.from_string(template_file.read())

    raise TemplateNotFound(
        ", ".join(relative_template_paths) if relative_template_paths else "unknown"
    )


def build_render_context(context: dict[str, Any]) -> dict[str, Any]:
    render_context = dict(context)
    for instance in Registry.get_instances().values():
        render_context.setdefault(instance.id, instance)
    return render_context


def stamp_reactive_markup(markup: str, component: BaseComponent) -> str:
    if not getattr(type(component), "_pjx_reactive", False):
        return markup

    from pyjinhx.reactive import pjx_load_value

    attrs = {
        "data-pjx-id": component.id,
        "data-pjx-type": type(component).__name__,
        "data-pjx-hash": component.state_hash(),
    }
    load_value = pjx_load_value(component)
    if load_value is not None:
        attrs["data-pjx-load"] = load_value
    reacts = getattr(type(component), "_pjx_reacts_to", frozenset())
    if reacts:
        attrs["data-pjx-reacts"] = " ".join(sorted(reacts))
    loading = getattr(type(component), "loading", None)
    if loading:
        attrs["data-pjx-loading"] = str(loading)
    return stamp_root_attributes(markup, attrs)


class Renderer:
    """
    Shared rendering engine used by `BaseComponent` rendering and HTML-like custom-tag rendering.

    This renderer centralizes:
    - Process-wide defaults and cached default-renderer factory
    - Jinja template loading (by component class or explicit file/source)
    - Expansion of PascalCase custom tags inside rendered markup
    - JavaScript collection/deduping and root-level script injection
    - Rendering of HTML-like source strings into component output
    """

    _default_environment: ClassVar[Environment | None] = None
    _default_js_mode: ClassVar[AssetMode] = AssetMode.INLINE
    _default_css_mode: ClassVar[AssetMode] = AssetMode.INLINE
    _default_runtime_url: ClassVar[str] = _DEFAULT_RUNTIME_URL
    _asset_url_resolver: ClassVar[AssetUrlResolver | None] = None
    _default_asset_dedup: ClassVar[bool] = False
    _default_renderers: ClassVar[dict[tuple[int, bool, AssetMode, AssetMode, int], object]] = {}

    @classmethod
    def peek_default_environment(cls) -> Environment | None:
        return cls._default_environment

    @classmethod
    def set_default_environment(
        cls, environment: Environment | str | os.PathLike[str] | None
    ) -> None:
        if environment is None or isinstance(environment, Environment):
            cls._default_environment = environment
        else:
            cls._default_environment = Environment(
                loader=FileSystemLoader(os.fspath(environment))
            )
        cls._default_renderers.clear()

    @classmethod
    def set_default_js_mode(cls, mode: AssetMode) -> None:
        cls._default_js_mode = mode
        cls._default_renderers.clear()

    @classmethod
    def set_default_css_mode(cls, mode: AssetMode) -> None:
        cls._default_css_mode = mode
        cls._default_renderers.clear()

    @classmethod
    def set_default_runtime_url(cls, url: str) -> None:
        cls._default_runtime_url = url
        cls._default_renderers.clear()

    @classmethod
    def set_asset_url_resolver(cls, resolver: AssetUrlResolver | None) -> None:
        cls._asset_url_resolver = resolver
        cls._default_renderers.clear()

    @classmethod
    def set_default_asset_dedup(cls, enabled: bool) -> None:
        cls._default_asset_dedup = enabled

    @classmethod
    def get_default_environment(cls) -> Environment:
        if cls._default_environment is None:
            root_dir = detect_root_directory()
            cls._default_environment = Environment(loader=FileSystemLoader(root_dir))
        return cls._default_environment

    @classmethod
    def get_default_renderer(
        cls,
        *,
        auto_id: bool = True,
        js_mode: AssetMode | None = None,
        css_mode: AssetMode | None = None,
    ):
        environment = cls.get_default_environment()
        effective_js_mode = js_mode if js_mode is not None else cls._default_js_mode
        effective_css_mode = css_mode if css_mode is not None else cls._default_css_mode
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
            renderer = cls(
                environment,
                auto_id=auto_id,
                js_mode=effective_js_mode,
                css_mode=effective_css_mode,
            )
            cls._default_renderers[cache_key] = renderer
        return renderer

    def __init__(
        self,
        environment: Environment,
        *,
        auto_id: bool = True,
        js_mode: AssetMode | None = None,
        css_mode: AssetMode | None = None,
    ) -> None:
        self._environment = environment
        self._auto_id = auto_id
        self._js_mode = js_mode if js_mode is not None else Renderer._default_js_mode
        self._css_mode = css_mode if css_mode is not None else Renderer._default_css_mode
        self._template_finder_cache: dict[str, object] = {}

    @property
    def environment(self) -> Environment:
        return self._environment

    def _resolve_asset_url(self, path: str) -> str:
        normalized_path = normalize_asset_path(path)
        if normalized_path == normalize_asset_path(runtime_asset_path()):
            return Renderer._default_runtime_url
        resolver = Renderer._asset_url_resolver
        if resolver is not None:
            return resolver(normalized_path)
        root = get_loader_root(self._environment)
        return make_default_asset_url_resolver(root)(normalized_path)

    def new_session(self) -> RenderSession:
        return RenderSession()

    def _find_template_for_tag(self, tag_name: str) -> str:
        loader_root = get_loader_root(self._environment)
        finder = get_finder_for_root(self, loader_root)
        return finder.find_template_for_tag(tag_name)

    def render_component_with_context(
        self,
        component: BaseComponent,
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
        template = load_template_for_component(
            self, component, template_source=template_source, template_path=template_path
        )

        render_context = build_render_context(context)
        rendered_markup = template.render(render_context)
        rendered_markup = expand_custom_tags(
            self,
            rendered_markup,
            base_context=render_context,
            session=session,
            emit_assets=emit_assets,
        )
        rendered_markup = stamp_reactive_markup(rendered_markup, component)

        if not emit_assets:
            return Markup(rendered_markup).unescape()

        policy = AssetPolicy(
            js_mode=self._js_mode,
            css_mode=self._css_mode,
            resolve_url=self._resolve_asset_url,
            loaded_assets=loaded_assets,
            dedup_enabled=Renderer._default_asset_dedup,
        )
        rendered_markup = apply_component_render_assets(
            component,
            rendered_markup,
            session,
            template_path=template_path,
            is_root=is_root,
            collect_component_js=collect_component_js,
            policy=policy,
            client=client,
        )
        return Markup(rendered_markup).unescape()

    def render(self, source: str) -> str:
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
            policy = AssetPolicy(
                js_mode=self._js_mode,
                css_mode=self._css_mode,
                resolve_url=self._resolve_asset_url,
                dedup_enabled=Renderer._default_asset_dedup,
            )
            rendered_markup = inject_assets(rendered_markup, session, policy=policy)
        return rendered_markup.strip()
