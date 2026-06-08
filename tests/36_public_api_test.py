import pyjinhx


def test_reactive_api_is_exported():
    from pyjinhx import (
        PJX_ASSETS_HEADER,
        PJX_MOUNTED_HEADER,
        ReactiveComponent,
        client_script,
        dependency_graph,
        dirty_keys,
        disable_layout_validation,
        enable_layout_validation,
        enable_reactive_dev,
        get_load_context,
        LayoutConfigurationError,
        layout_validation_enabled,
        validate_layout_registry,
        instance_key,
        mutates,
        oob_swaps,
        parse_loaded_assets,
        StateKey,
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
    assert issubclass(ReactiveComponent, pyjinhx.BaseComponent)
    assert issubclass(StateKey, str)


def test_names_in_all():
    for name in (
        "oob_swaps",
        "ReactiveComponent",
        "client_script",
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
        "LayoutConfigurationError",
        "validate_layout_registry",
        "validate_root_is_layout",
        "enable_layout_validation",
        "disable_layout_validation",
        "layout_validation_enabled",
    ):
        assert name in pyjinhx.__all__
