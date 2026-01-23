import logging

from pyjinhx import Registry
from tests.ui.unified_component import UnifiedComponent


def test_registry_clear():
    Registry.clear_instances()

    UnifiedComponent(id="clear-test-1", text="First")
    UnifiedComponent(id="clear-test-2", text="Second")

    assert len(Registry.get_instances()) == 2

    Registry.clear_instances()

    assert len(Registry.get_instances()) == 0
    key1 = Registry.make_key("UnifiedComponent", "clear-test-1")
    key2 = Registry.make_key("UnifiedComponent", "clear-test-2")
    assert key1 not in Registry.get_instances()
    assert key2 not in Registry.get_instances()


def test_registry_get_returns_reference():
    Registry.clear_instances()

    component = UnifiedComponent(id="ref-test-1", text="Test")

    registry1 = Registry.get_instances()
    registry2 = Registry.get_instances()

    key = Registry.make_key("UnifiedComponent", "ref-test-1")
    assert registry1 is registry2
    assert registry1[key] == component
    assert registry2[key] == component


def test_registry_after_component_deletion():
    Registry.clear_instances()

    component = UnifiedComponent(id="delete-test-1", text="Test")

    key = Registry.make_key("UnifiedComponent", "delete-test-1")
    assert key in Registry.get_instances()

    del component

    assert key in Registry.get_instances()


def test_registry_with_multiple_components():
    Registry.clear_instances()

    for i in range(5):
        UnifiedComponent(id=f"multi-{i}", text=f"Component {i}")

    registry = Registry.get_instances()

    assert len(registry) == 5
    for i in range(5):
        key = Registry.make_key("UnifiedComponent", f"multi-{i}")
        assert key in registry
        assert registry[key].text == f"Component {i}"


def test_duplicate_component_id_warning(caplog):
    logging.getLogger("pyjinhx").setLevel(logging.WARNING)

    Registry.clear_instances()

    key = Registry.make_key("UnifiedComponent", "duplicate-1")
    component1 = UnifiedComponent(id="duplicate-1", text="First")
    assert Registry.get_instances()[key] == component1

    component2 = UnifiedComponent(id="duplicate-1", text="Second")

    assert len(Registry.get_instances()) == 1
    assert Registry.get_instances()[key] == component2

    assert "While registering" in caplog.text
    assert "duplicate-1" in caplog.text


def test_different_component_types_same_id_no_collision():
    """Test that different component types can use the same id without collision."""
    from pyjinhx import BaseComponent

    Registry.clear_instances()

    class Card(BaseComponent):
        id: str
        label: str = ""

    class Button(BaseComponent):
        id: str
        label: str = ""

    Card(id="shared", label="Card Label")
    Button(id="shared", label="Button Label")

    # Both should coexist in the registry
    assert len(Registry.get_instances()) == 2

    card_key = Registry.make_key("Card", "shared")
    button_key = Registry.make_key("Button", "shared")

    assert card_key in Registry.get_instances()
    assert button_key in Registry.get_instances()

    assert Registry.get_instances()[card_key].label == "Card Label"
    assert Registry.get_instances()[button_key].label == "Button Label"
