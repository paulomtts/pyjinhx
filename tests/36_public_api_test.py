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
        InvalidationHub,
        LoadCache,
        LoadContext,
        LoadedAssets,
        MountedManifest,
        MutationTracker,
        ReactiveComponent,
        client_script,
        dependency_graph,
        enable_reactive_dev,
        mutates,
        oob_swaps,
        StateKey,
        PyJinhxSettings,
        configure_pyjinhx,
        shutdown_pyjinhx,
        pyjinhx_lifespan,
        setup,
    )

    assert PJX_MOUNTED_HEADER == "X-PJX-Mounted"
    assert PJX_ASSETS_HEADER == "X-PJX-Assets"
    assert callable(oob_swaps)
    assert callable(client_script)
    assert callable(mutates)
    assert callable(dependency_graph)
    assert callable(enable_reactive_dev)
    assert callable(LoadedAssets.parse)
    assert callable(MountedManifest.parse)
    assert callable(MountedManifest.is_present)
    assert callable(LoadCache.set_scope)
    assert callable(LoadCache.scope)
    assert callable(InvalidationHub.set_backend)
    assert callable(InvalidationHub.start_listener)
    assert callable(InvalidationHub.stop_listener)
    assert callable(setup)
    assert callable(PyJinhxSettings.from_env)
    assert callable(configure_pyjinhx)
    assert callable(shutdown_pyjinhx)
    assert callable(pyjinhx_lifespan)
    assert CacheScope.REQUEST == "request"
    assert issubclass(ClientBackend, ABC)
    assert issubclass(InvalidationBackend, ABC)
    assert issubclass(FastAPIClientBackend, ClientBackend)
    assert callable(ClientBackend.scope)
    assert callable(ClientBackend.current)
    assert callable(LoadContext.current)
    assert callable(LoadContext.bind)
    assert callable(StateKey.instance_key)
    assert callable(StateKey.dirty_keys)
    assert callable(MutationTracker.record)
    assert issubclass(ReactiveComponent, pyjinhx.BaseComponent)
    assert issubclass(StateKey, str)


def test_names_in_all():
    for name in (
        "oob_swaps",
        "ReactiveComponent",
        "client_script",
        "LoadedAssets",
        "MountedManifest",
        "PJX_MOUNTED_HEADER",
        "PJX_ASSETS_HEADER",
        "StateKey",
        "mutates",
        "mutation_scope",
        "LoadContext",
        "enable_reactive_dev",
        "disable_reactive_dev",
        "dependency_graph",
        "format_dependency_graph",
        "CacheScope",
        "LoadCache",
        "MutationTracker",
        "InvalidationBackend",
        "InvalidationHub",
        "PyJinhxSettings",
        "configure_pyjinhx",
        "shutdown_pyjinhx",
        "pyjinhx_lifespan",
        "setup",
        "ClientBackend",
        "FastAPIClientBackend",
    ):
        assert name in pyjinhx.__all__
