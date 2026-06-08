import pyjinhx


def test_reactive_api_is_exported():
    from pyjinhx import (
        PJX_MOUNTED_HEADER,
        ReactiveComponent,
        client_script,
        dependency_graph,
        dirty_keys,
        enable_reactive_dev,
        get_load_context,
        instance_key,
        mutates,
        oob_swaps,
        StateKey,
    )

    assert PJX_MOUNTED_HEADER == "X-PJX-Mounted"
    assert callable(oob_swaps)
    assert callable(client_script)
    assert callable(mutates)
    assert callable(dependency_graph)
    assert callable(enable_reactive_dev)
    assert callable(get_load_context)
    assert callable(dirty_keys)
    assert callable(instance_key)
    assert issubclass(ReactiveComponent, pyjinhx.BaseComponent)
    assert issubclass(StateKey, str)


def test_names_in_all():
    for name in (
        "oob_swaps",
        "ReactiveComponent",
        "client_script",
        "PJX_MOUNTED_HEADER",
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
    ):
        assert name in pyjinhx.__all__
