import pyjinhx
from pyjinhx import (
    AssetMode,
    BaseComponent,
    MutationKey,
    PjxContext,
    PjxKey,
    PjxSettings,
    ReactiveComponent,
    Registry,
    Renderer,
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
    "MutationKey",
    "PjxKey",
    "PjxContext",
    "PjxSettings",
    "AssetMode",
}


def test_public_api_is_exactly_the_curated_set():
    assert set(pyjinhx.__all__) == PUBLIC_API
    assert len(pyjinhx.__all__) == len(PUBLIC_API)  # no duplicates


def test_public_symbols_are_correct():
    assert issubclass(ReactiveComponent, BaseComponent)
    assert issubclass(MutationKey, str)
    assert AssetMode.INLINE is not None
    assert PjxKey.__name__ == "PjxKey"
    for fn in (setup, mutates, PjxSettings.from_env,
               Renderer.set_default_environment, Registry.request_scope,
               PjxContext.current):
        assert callable(fn)


def test_internals_are_not_in_the_public_surface():
    # advanced/internal building blocks must NOT leak into the top-level API
    for name in (
        "CacheScope", "client_script", "oob_swaps", "LoadCache", "InvalidationHub",
        "InvalidationBackend", "MutationTracker", "Finder", "Parser", "Tag",
        "ClientBackend", "FastAPIClientBackend", "MountedManifest", "TriggerManifest",
        "LoadedAssets", "PJX_MOUNTED_HEADER", "PJX_ASSETS_HEADER", "PJX_TRIGGER_HEADER",
        "configure_pyjinhx", "shutdown_pyjinhx",
        "enable_reactive_dev", "disable_reactive_dev", "dependency_graph",
        "format_dependency_graph", "AssetManifest", "RenderSession", "asset_manifest",
        "default_asset_url", "hashed_filename", "make_default_asset_url_resolver",
        "resolver_with_hash", "runtime_asset_path", "DEFAULT_RUNTIME_URL",
    ):
        assert name not in pyjinhx.__all__
        assert not hasattr(pyjinhx, name)


def test_internals_remain_importable_from_submodules():
    # still available for advanced use — just not on the curated surface
    from pyjinhx.cache import CacheScope, InvalidationHub, LoadCache  # noqa: F401
    from pyjinhx.client import (  # noqa: F401
        PJX_MOUNTED_HEADER,
        ClientBackend,
        MountedManifest,
        client_script,
    )
    from pyjinhx.config import configure_pyjinhx, shutdown_pyjinhx  # noqa: F401
    from pyjinhx.dev import dependency_graph, enable_reactive_dev  # noqa: F401
    from pyjinhx.integrations.fastapi import FastAPIClientBackend  # noqa: F401
    from pyjinhx.reactive import oob_swaps, reactive_response  # noqa: F401
