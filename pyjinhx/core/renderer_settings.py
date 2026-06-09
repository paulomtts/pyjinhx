from __future__ import annotations

import os
from typing import ClassVar

from jinja2 import Environment, FileSystemLoader

from .assets import (
    DEFAULT_RUNTIME_URL as _DEFAULT_RUNTIME_URL,
    AssetMode,
    AssetUrlResolver,
    asset_mode_from_inline,
)
from ..utils import detect_root_directory


class RendererSettings:
    """Process-wide renderer defaults and cached default-renderer factory."""

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
    def set_default_inline_js(cls, inline_js: bool) -> None:
        cls.set_default_js_mode(asset_mode_from_inline(inline_js))

    @classmethod
    def set_default_inline_css(cls, inline_css: bool) -> None:
        cls.set_default_css_mode(asset_mode_from_inline(inline_css))

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
        inline_js: bool | None = None,
        inline_css: bool | None = None,
        js_mode: AssetMode | None = None,
        css_mode: AssetMode | None = None,
    ):
        from .renderer import Renderer

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
