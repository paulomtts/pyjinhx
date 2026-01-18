from pyjinhx import Registry
from tests.ui.unified_component import UnifiedComponent
import logging


def test_registry_clear():
    Registry.clear()
    
    UnifiedComponent(id="clear-test-1", text="First")
    UnifiedComponent(id="clear-test-2", text="Second")
    
    assert len(Registry.get()) == 2
    
    Registry.clear()
    
    assert len(Registry.get()) == 0
    assert "clear-test-1" not in Registry.get()
    assert "clear-test-2" not in Registry.get()


def test_registry_get_returns_reference():
    Registry.clear()
    
    component = UnifiedComponent(id="ref-test-1", text="Test")
    
    registry1 = Registry.get()
    registry2 = Registry.get()
    
    assert registry1 is registry2
    assert registry1["ref-test-1"] == component
    assert registry2["ref-test-1"] == component


def test_registry_after_component_deletion():
    Registry.clear()
    
    component = UnifiedComponent(id="delete-test-1", text="Test")
    
    assert "delete-test-1" in Registry.get()
    
    del component
    
    assert "delete-test-1" in Registry.get()


def test_registry_with_multiple_components():
    Registry.clear()
    
    for i in range(5):
        UnifiedComponent(id=f"multi-{i}", text=f"Component {i}")
    
    registry = Registry.get()
    
    assert len(registry) == 5
    for i in range(5):
        assert f"multi-{i}" in registry
        assert registry[f"multi-{i}"].text == f"Component {i}"


def test_duplicate_component_id_warning(caplog):
    logging.getLogger("pyjinhx").setLevel(logging.WARNING)

    Registry.clear()

    component1 = UnifiedComponent(id="duplicate-1", text="First")
    assert Registry.get()["duplicate-1"] == component1

    component2 = UnifiedComponent(id="duplicate-1", text="Second")

    assert len(Registry.get()) == 1
    assert Registry.get()["duplicate-1"] == component2

    assert "While registering" in caplog.text
    assert "duplicate-1" in caplog.text

