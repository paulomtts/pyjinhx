import pytest

from pyjinhx import (
    BaseComponent,
    LayoutConfigurationError,
    Registry,
    disable_layout_validation,
    enable_layout_validation,
    validate_layout_registry,
)
from tests.ui.reactive.reactive_counter import ReactiveCounter


@pytest.fixture
def isolated_class_registry():
    saved = Registry.get_classes().copy()
    Registry.clear_classes()
    yield
    Registry.clear_classes()
    for component_class in saved.values():
        Registry.register_class(component_class)


@pytest.fixture(autouse=True)
def reset_layout_validation():
    disable_layout_validation()
    yield
    disable_layout_validation()


def test_layout_declared_flag_distinguishes_inheritance(isolated_class_registry):
    class LayoutPage(BaseComponent, base_layout=True):
        pass

    class LayoutAdminPage(LayoutPage):
        pass

    assert LayoutPage._pjx_layout_declared is True
    assert LayoutPage._pjx_layout is True
    assert LayoutAdminPage._pjx_layout_declared is False
    assert LayoutAdminPage._pjx_layout is True


def test_validate_layout_registry_passes_with_one_declared_layout(
    isolated_class_registry,
):
    class AppShell(BaseComponent, base_layout=True):
        pass

    validate_layout_registry()


def test_validate_layout_registry_fails_with_zero_declared_layouts(
    isolated_class_registry,
):
    class Widget(BaseComponent):
        pass

    with pytest.raises(LayoutConfigurationError, match="found 0"):
        validate_layout_registry()


def test_validate_layout_registry_fails_with_two_declared_layouts(
    isolated_class_registry,
):
    class LayoutPage(BaseComponent, base_layout=True):
        pass

    class LayoutDashboard(BaseComponent, base_layout=True):
        pass

    with pytest.raises(LayoutConfigurationError, match="found 2"):
        validate_layout_registry()


def test_validate_layout_registry_ignores_inherited_layout_subclass(
    isolated_class_registry,
):
    class LayoutPage(BaseComponent, base_layout=True):
        pass

    class LayoutAdminPage(LayoutPage):
        pass

    validate_layout_registry()


def test_enable_layout_validation_rejects_non_layout_root(isolated_class_registry):
    class LayoutPage(BaseComponent, base_layout=True):
        pass

    class PlainShell(BaseComponent):
        pass

    enable_layout_validation()
    with pytest.raises(LayoutConfigurationError, match="Root render must use"):
        PlainShell(id="shell")._render(source="<html><body>hi</body></html>")


def test_enable_layout_validation_allows_layout_root(isolated_class_registry):
    class LayoutPage(BaseComponent, base_layout=True):
        pass

    enable_layout_validation()
    html = str(LayoutPage(id="page")._render(source="<html><body>hi</body></html>"))
    assert "htmx:configRequest" in html


def test_enable_layout_validation_allows_layout_subclass_root(isolated_class_registry):
    class LayoutPage(BaseComponent, base_layout=True):
        pass

    class LayoutAdminPage(LayoutPage):
        pass

    enable_layout_validation()
    html = str(
        LayoutAdminPage(id="admin")._render(source="<html><body>hi</body></html>")
    )
    assert "htmx:configRequest" in html


def test_layout_validation_disabled_allows_non_layout_root(isolated_class_registry):
    class PlainShell(BaseComponent):
        pass

    html = str(PlainShell(id="shell")._render(source="<html><body>hi</body></html>"))
    assert "htmx:configRequest" not in html


def test_reactive_partial_skips_root_layout_validation():
    enable_layout_validation()
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    rendered = str(
        ReactiveCounter.load().render(dirtied={"todos"}, mounted=manifest)
    )
    assert "<script" not in rendered
