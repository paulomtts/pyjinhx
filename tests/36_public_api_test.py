from abc import ABC

import pyjinhx


def test_reactive_api_is_exported():
    from pyjinhx import (
        PJX_ASSETS_HEADER,
        PJX_MOUNTED_HEADER,
        CacheScope,
        ClientBackend,
        FastAPIClientBackend,
        InvalidationBackend,
        ReactiveComponent,
        fastapi_client_backend,
        client_has_mounted_manifest,
        client_script,
        dependency_graph,
        dirty_keys,
        enable_reactive_dev,
        get_load_cache_scope,
        get_load_context,
        instance_key,
        mutates,
        oob_swaps,
        parse_loaded_assets,
        set_invalidation_backend,
        set_load_cache_scope,
        start_invalidation_listener,
        StateKey,
        stop_invalidation_listener,
    )

    assert PJX_MOUNTED_HEADER == "X-PJX-Mounted"
    assert PJX_ASSETS_HEADER == "X-PJX-Assets"
    assert callable(oob_swaps)
    assert callable(client_script)
    assert callable(mutates)
    assert callable(dependency_graph)
    assert callable(enable_reactive_dev)
    assert callable(get_load_context)
    assert callable(dirty_keys)
    assert callable(instance_key)
    assert callable(parse_loaded_assets)
    assert callable(client_has_mounted_manifest)
    assert callable(set_load_cache_scope)
    assert callable(get_load_cache_scope)
    assert callable(set_invalidation_backend)
    assert callable(start_invalidation_listener)
    assert callable(stop_invalidation_listener)
    assert CacheScope.REQUEST == "request"
    assert issubclass(ClientBackend, ABC)
    assert issubclass(InvalidationBackend, ABC)
    assert issubclass(FastAPIClientBackend, ClientBackend)
    assert callable(fastapi_client_backend)
    assert callable(ClientBackend.scope)
    assert callable(ClientBackend.current)
    assert issubclass(ReactiveComponent, pyjinhx.BaseComponent)
    assert issubclass(StateKey, str)


def test_names_in_all():
    for name in (
        "oob_swaps",
        "ReactiveComponent",
        "client_script",
        "client_has_mounted_manifest",
        "PJX_MOUNTED_HEADER",
        "PJX_ASSETS_HEADER",
        "parse_loaded_assets",
        "StateKey",
        "instance_key",
        "dirty_keys",
        "mutates",
        "mutation_scope",
        "LoadContext",
        "get_load_context",
        "load_scope",
        "enable_reactive_dev",
        "disable_reactive_dev",
        "dependency_graph",
        "format_dependency_graph",
        "CacheScope",
        "get_load_cache_scope",
        "set_load_cache_scope",
        "InvalidationBackend",
        "set_invalidation_backend",
        "start_invalidation_listener",
        "stop_invalidation_listener",
        "ClientBackend",
        "FastAPIClientBackend",
        "fastapi_client_backend",
    ):
        assert name in pyjinhx.__all__
