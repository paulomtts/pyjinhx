import logging

from pyjinhx import Registry
from tests.ui.unified_component import UnifiedComponent


def test_request_scope_creates_fresh_registry():
    Registry.clear_instances()

    UnifiedComponent(id="outside-scope", text="Outside")

    with Registry.request_scope():
        assert len(Registry.get_instances()) == 0
        key_outside = Registry.make_key("UnifiedComponent", "outside-scope")
        assert key_outside not in Registry.get_instances()

        UnifiedComponent(id="inside-scope", text="Inside")
        assert len(Registry.get_instances()) == 1
        key_inside = Registry.make_key("UnifiedComponent", "inside-scope")
        assert key_inside in Registry.get_instances()

    key_outside = Registry.make_key("UnifiedComponent", "outside-scope")
    key_inside = Registry.make_key("UnifiedComponent", "inside-scope")
    assert key_outside in Registry.get_instances()
    assert key_inside not in Registry.get_instances()


def test_request_scope_no_warnings_on_reuse(caplog):
    logging.getLogger("pyjinhx").setLevel(logging.WARNING)

    Registry.clear_instances()

    with Registry.request_scope():
        UnifiedComponent(id="reused-id", text="First request")

    with Registry.request_scope():
        UnifiedComponent(id="reused-id", text="Second request")

    assert "Overwriting" not in caplog.text


def test_request_scope_nested():
    Registry.clear_instances()

    with Registry.request_scope():
        UnifiedComponent(id="outer", text="Outer")
        key_outer = Registry.make_key("UnifiedComponent", "outer")
        assert key_outer in Registry.get_instances()

        with Registry.request_scope():
            assert key_outer not in Registry.get_instances()
            UnifiedComponent(id="inner", text="Inner")
            key_inner = Registry.make_key("UnifiedComponent", "inner")
            assert key_inner in Registry.get_instances()

        assert key_outer in Registry.get_instances()
        key_inner = Registry.make_key("UnifiedComponent", "inner")
        assert key_inner not in Registry.get_instances()


def test_request_scope_restores_on_exception():
    Registry.clear_instances()

    UnifiedComponent(id="before-exception", text="Before")

    try:
        with Registry.request_scope():
            UnifiedComponent(id="during-exception", text="During")
            raise ValueError("Test exception")
    except ValueError:
        pass

    key_before = Registry.make_key("UnifiedComponent", "before-exception")
    key_during = Registry.make_key("UnifiedComponent", "during-exception")
    assert key_before in Registry.get_instances()
    assert key_during not in Registry.get_instances()
