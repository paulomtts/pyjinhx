import pyjinhx


def test_reactive_api_is_exported():
    from pyjinhx import (
        Layout,
        PJX_MOUNTED_HEADER,
        client_script,
        oob_swaps,
    )

    assert PJX_MOUNTED_HEADER == "X-PJX-Mounted"
    assert callable(oob_swaps)
    assert callable(client_script)
    assert issubclass(Layout, pyjinhx.BaseComponent)


def test_names_in_all():
    for name in ("oob_swaps", "Layout", "client_script", "PJX_MOUNTED_HEADER"):
        assert name in pyjinhx.__all__
