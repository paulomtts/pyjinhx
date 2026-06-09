import pyjinhx
from pyjinhx import (
    AssetMode,
    BaseComponent,
    CacheScope,
    LoadContext,
    PjxLoad,
    PyJinhxSettings,
    ReactiveComponent,
    Registry,
    Renderer,
    StateKey,
    client_script,
    mutates,
    setup,
)

PUBLIC_API = {
    "BaseComponent",
    "ReactiveComponent",
    "Renderer",
    "setup",
    "Registry",
    "mutates",
    "StateKey",
    "PjxLoad",
    "LoadContext",
    "PyJinhxSettings",
    "CacheScope",
    "AssetMode",
    "client_script",
}


def test_public_api_is_exactly_the_curated_set():
    assert set(pyjinhx.__all__) == PUBLIC_API
    assert len(pyjinhx.__all__) == len(PUBLIC_API)  # no duplicates


def test_public_symbols_are_correct():
    assert issubclass(ReactiveComponent, BaseComponent)
    assert issubclass(StateKey, str)
    assert CacheScope.REQUEST == "request"
    assert AssetMode.INLINE is not None
    assert PjxLoad.__name__ == "PjxLoad"
    for fn in (setup, mutates, client_script, PyJinhxSettings.from_env,
               Renderer.set_default_environment, Registry.request_scope,
               LoadContext.current):
        assert callable(fn)


def test_internals_are_not_in_the_public_surface():
    # advanced/internal building blocks must NOT leak into the top-level API
    for name in (
        "oob_swaps", "LoadCache", "InvalidationHub", "InvalidationBackend",
        "MutationTracker", "Finder", "Parser", "Tag", "ClientBackend",
        "FastAPIClientBackend", "MountedManifest", "TriggerManifest", "LoadedAssets",
        "PJX_MOUNTED_HEADER", "PJX_ASSETS_HEADER", "PJX_TRIGGER_HEADER",
        "configure_pyjinhx", "shutdown_pyjinhx", "pyjinhx_lifespan",
        "enable_reactive_dev", "disable_reactive_dev", "dependency_graph",
        "format_dependency_graph", "AssetManifest", "RenderSession", "asset_manifest",
        "default_asset_url", "hashed_filename", "make_default_asset_url_resolver",
        "resolver_with_hash", "runtime_asset_path", "DEFAULT_RUNTIME_URL",
    ):
        assert name not in pyjinhx.__all__
        assert not hasattr(pyjinhx, name)


def test_internals_remain_importable_from_submodules():
    # still available for advanced use — just not on the curated surface
    from pyjinhx.cache import InvalidationHub, LoadCache  # noqa: F401
    from pyjinhx.client import PJX_MOUNTED_HEADER, ClientBackend, MountedManifest  # noqa: F401
    from pyjinhx.config import configure_pyjinhx, pyjinhx_lifespan, shutdown_pyjinhx  # noqa: F401
    from pyjinhx.dev import dependency_graph, enable_reactive_dev  # noqa: F401
    from pyjinhx.integrations.fastapi import FastAPIClientBackend  # noqa: F401
    from pyjinhx.reactive import oob_swaps  # noqa: F401
