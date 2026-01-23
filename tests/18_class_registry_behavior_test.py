from pyjinhx import BaseComponent, Registry


def test_class_registered_at_definition_time():
    """Test that classes are registered automatically when defined, before instantiation."""

    class TestButton(BaseComponent):
        id: str
        text: str

    classes = Registry.get_classes()
    assert "TestButton" in classes
    assert classes["TestButton"] is TestButton


def test_multiple_classes_registered():
    """Test that multiple component classes can be registered."""

    class Button(BaseComponent):
        id: str
        text: str

    class Card(BaseComponent):
        id: str
        title: str

    class Modal(BaseComponent):
        id: str
        content: str

    classes = Registry.get_classes()
    assert "Button" in classes
    assert "Card" in classes
    assert "Modal" in classes
    assert classes["Button"] is Button
    assert classes["Card"] is Card
    assert classes["Modal"] is Modal


def test_class_registry_separate_from_instance_registry():
    """Test that class registry and instance registry are independent."""
    Registry.clear_instances()

    class TestComponent(BaseComponent):
        id: str
        value: str

    classes_before = Registry.get_classes()
    instances_before = Registry.get_instances()

    assert "TestComponent" in classes_before
    assert len(instances_before) == 0

    TestComponent(id="inst-1", value="First")
    TestComponent(id="inst-2", value="Second")

    classes_after = Registry.get_classes()
    instances_after = Registry.get_instances()

    assert "TestComponent" in classes_after
    assert classes_after["TestComponent"] is TestComponent
    assert len(instances_after) == 2
    key1 = Registry.make_key("TestComponent", "inst-1")
    key2 = Registry.make_key("TestComponent", "inst-2")
    assert key1 in instances_after
    assert key2 in instances_after


def test_class_registry_persists_across_instantiations():
    """Test that class registry persists even when instances are cleared."""

    class PersistentComponent(BaseComponent):
        id: str
        data: str

    classes = Registry.get_classes()
    assert "PersistentComponent" in classes

    Registry.clear_instances()

    classes_after_clear = Registry.get_classes()
    assert "PersistentComponent" in classes_after_clear
    assert classes_after_clear["PersistentComponent"] is PersistentComponent

    instances_after_clear = Registry.get_instances()
    assert len(instances_after_clear) == 0


def test_nested_class_registration():
    """Test that nested component classes are also registered."""

    class OuterComponent(BaseComponent):
        id: str
        label: str

    class InnerComponent(BaseComponent):
        id: str
        content: OuterComponent

    classes = Registry.get_classes()
    assert "OuterComponent" in classes
    assert "InnerComponent" in classes
    assert classes["OuterComponent"] is OuterComponent
    assert classes["InnerComponent"] is InnerComponent


def test_inherited_classes_registered():
    """Test that classes inheriting from BaseComponent subclasses are also registered."""

    class BaseButton(BaseComponent):
        id: str
        text: str

    class PrimaryButton(BaseButton):
        variant: str = "primary"

    class SecondaryButton(BaseButton):
        variant: str = "secondary"

    classes = Registry.get_classes()
    assert "BaseButton" in classes
    assert "PrimaryButton" in classes
    assert "SecondaryButton" in classes
    assert classes["BaseButton"] is BaseButton
    assert classes["PrimaryButton"] is PrimaryButton
    assert classes["SecondaryButton"] is SecondaryButton
