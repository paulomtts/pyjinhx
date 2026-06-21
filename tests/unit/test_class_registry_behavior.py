import importlib.util
import sys

import pytest

from pyjinhx import BaseComponent, Registry

_COLLISION_SRC = """\
from pyjinhx import BaseComponent

class {class_name}(BaseComponent):
    id: str = ""
"""


def _import_component_file(filepath, module_name):
    """Import a component file by path, like ComponentAutodiscover does."""
    spec = importlib.util.spec_from_file_location(module_name, str(filepath))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_class_registered_at_definition_time():
    """Test that classes are registered automatically when defined, before instantiation."""

    class TestButton(BaseComponent):
        text: str

    classes = Registry.get_classes()
    assert "TestButton" in classes
    assert classes["TestButton"] is TestButton


def test_multiple_classes_registered():
    """Test that multiple component classes can be registered."""

    class RegistryButton(BaseComponent):
        text: str

    class RegistryCard(BaseComponent):
        title: str

    class RegistryModal(BaseComponent):
        content: str

    classes = Registry.get_classes()
    assert "RegistryButton" in classes
    assert "RegistryCard" in classes
    assert "RegistryModal" in classes
    assert classes["RegistryButton"] is RegistryButton
    assert classes["RegistryCard"] is RegistryCard
    assert classes["RegistryModal"] is RegistryModal


def test_class_registry_separate_from_instance_registry():
    """Test that class registry and instance registry are independent."""
    Registry.clear_instances()

    class TestComponent(BaseComponent):
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
        label: str

    class InnerComponent(BaseComponent):
        content: OuterComponent

    classes = Registry.get_classes()
    assert "OuterComponent" in classes
    assert "InnerComponent" in classes
    assert classes["OuterComponent"] is OuterComponent
    assert classes["InnerComponent"] is InnerComponent


def test_inherited_classes_registered():
    """Test that classes inheriting from BaseComponent subclasses are also registered."""

    class BaseButton(BaseComponent):
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


def test_same_name_from_different_files_raises(tmp_path):
    """Two same-name classes from different source files collide loudly."""
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text(_COLLISION_SRC.format(class_name="CollisionWidget"))
    second.write_text(_COLLISION_SRC.format(class_name="CollisionWidget"))

    _import_component_file(first, "_test_collision_first")
    with pytest.raises(TypeError) as exc_info:
        _import_component_file(second, "_test_collision_second")

    message = str(exc_info.value)
    assert "CollisionWidget" in message
    assert "first.py" in message
    assert "second.py" in message
    assert "pjx_replace=True" in message

    # The original registration survives the failed overwrite.
    assert Registry.get_class("CollisionWidget").__module__ == "_test_collision_first"


def test_reregistering_from_same_file_is_allowed(tmp_path):
    """Re-executing the same module (test reruns, hot reload) does not raise."""
    module_file = tmp_path / "reloaded.py"
    module_file.write_text(_COLLISION_SRC.format(class_name="ReloadedWidget"))

    first = _import_component_file(module_file, "_test_reload_widget")
    second = _import_component_file(module_file, "_test_reload_widget")

    assert first.ReloadedWidget is not second.ReloadedWidget
    assert Registry.get_class("ReloadedWidget") is second.ReloadedWidget


def test_pjx_replace_keyword_shadows_cross_file_registration(tmp_path):
    """pjx_replace=True intentionally shadows a same-name class from elsewhere."""
    module_file = tmp_path / "shadowed.py"
    module_file.write_text(_COLLISION_SRC.format(class_name="ShadowedWidget"))
    _import_component_file(module_file, "_test_shadowed_widget")

    class ShadowedWidget(BaseComponent, pjx_replace=True):
        id: str = ""

    assert Registry.get_class("ShadowedWidget") is ShadowedWidget
