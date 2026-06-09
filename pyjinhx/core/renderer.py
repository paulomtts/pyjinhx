from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jinja2 import Environment
from markupsafe import Markup

from .assets import (
    AssetMode,
    RenderSession,
    asset_mode_from_inline,
    make_default_asset_url_resolver,
    runtime_asset_path,
)
from .tags import Parser
from .assets import (
    apply_component_render_assets,
    inject_assets,
    normalize_asset_path,
)
from .render_context import build_render_context, stamp_reactive_markup
from .renderer_settings import RendererSettings
from .tags import expand_custom_tags, render_tag_node
from .template_load import find_template_for_tag, load_template_for_component

if TYPE_CHECKING:
    from .base import BaseComponent


class Renderer(RendererSettings):
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
        from .template_load import get_loader_root

        root = get_loader_root(self._environment)
        return make_default_asset_url_resolver(root)(normalized_path)

    def new_session(self) -> RenderSession:
        return RenderSession()

    def _load_template_for_component(
        self,
        component: BaseComponent,
        *,
        template_source: str | None,
        template_path: str | None,
    ):
        return load_template_for_component(
            self,
            component,
            template_source=template_source,
            template_path=template_path,
        )

    def _find_template_for_tag(self, tag_name: str) -> str:
        return find_template_for_tag(self, tag_name)

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
        template = self._load_template_for_component(
            component, template_source=template_source, template_path=template_path
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

        rendered_markup = apply_component_render_assets(
            component,
            rendered_markup,
            session,
            template_path=template_path,
            is_root=is_root,
            collect_component_js=collect_component_js,
            js_mode=self._js_mode,
            css_mode=self._css_mode,
            resolve_url=self._resolve_asset_url,
            loaded_assets=loaded_assets,
            dedup_enabled=Renderer._default_asset_dedup,
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
            rendered_markup = inject_assets(
                rendered_markup,
                session,
                js_mode=self._js_mode,
                css_mode=self._css_mode,
                resolve_url=self._resolve_asset_url,
                dedup_enabled=Renderer._default_asset_dedup,
            )
        return rendered_markup.strip()
