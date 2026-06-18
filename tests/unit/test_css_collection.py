import pytest

from pyjinhx import AssetMode, Renderer
from tests.ui.unified_component import UnifiedComponent
from tests.ui.reactive.reactive_counter import ReactiveCounter


@pytest.fixture(autouse=True)
def reset_renderer_defaults():
    original_js = Renderer._default_js_mode
    original_css = Renderer._default_css_mode
    Renderer._default_renderers.clear()
    yield
    Renderer.set_default_js_mode(original_js)
    Renderer.set_default_css_mode(original_css)
    Renderer._default_renderers.clear()


def test_css_auto_discovery():
    component = UnifiedComponent(id="css-1", text="Styled")

    rendered = str(component.render())

    assert "<style>" in rendered
    assert ".test-component { color: red; }" in rendered


def test_css_injected_before_html():
    component = UnifiedComponent(id="css-2", text="Styled")

    rendered = str(component.render())

    style_pos = rendered.find("<style>")
    div_pos = rendered.find("<div")
    assert style_pos < div_pos, "Styles should be injected before HTML"


def test_css_deduplication():
    nested = UnifiedComponent(id="css-nested-1", text="Nested")
    component = UnifiedComponent(id="css-parent-1", title="Parent", items=[nested])

    rendered = str(component.render())

    assert rendered.count(".test-component { color: red; }") == 1


def test_extra_css():
    component = UnifiedComponent(
        id="css-extra-1",
        text="Extra CSS",
        css=["tests/ui/extra_style.css"],
    )

    rendered = str(component.render())

    assert ".test-component { color: red; }" in rendered
    assert ".extra { font-weight: bold; }" in rendered


def test_extra_css_deduplication():
    component = UnifiedComponent(
        id="css-dedup-1",
        text="Dedup",
        css=["tests/ui/extra_style.css", "tests/ui/extra_style.css"],
    )

    rendered = str(component.render())

    assert rendered.count(".extra { font-weight: bold; }") == 1


def test_missing_extra_css_warns(caplog):
    import logging

    component = UnifiedComponent(
        id="css-missing-1",
        text="Missing",
        css=["tests/ui/nonexistent.css"],
    )

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        rendered = str(component.render())

    assert "<div" in rendered
    assert "nonexistent" not in rendered
    assert any("nonexistent.css" in record.message for record in caplog.records)


def test_css_mode_none_disables_injection():
    renderer = Renderer.get_default_renderer(css_mode=AssetMode.NONE)
    component = UnifiedComponent(id="css-off-1", text="No CSS")

    rendered = str(component._render(_renderer=renderer))

    assert "<style>" not in rendered


def test_css_order_styles_before_scripts():
    component = UnifiedComponent(id="css-order-1", text="Order Test")

    rendered = str(component.render())

    style_pos = rendered.find("<style>")
    script_pos = rendered.find("<script>")
    assert style_pos < script_pos, "Styles should come before scripts"


def test_none_mode_stays_silent():
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.NONE,
        css_mode=AssetMode.NONE,
    )
    rendered = str(
        UnifiedComponent(id="none-1", text="Silent")._render(_renderer=renderer)
    )

    assert "<style>" not in rendered
    assert "<script" not in rendered
    assert "<link" not in rendered


def test_set_default_js_mode_none():
    Renderer.set_default_js_mode(AssetMode.NONE)
    renderer = Renderer.get_default_renderer()
    assert renderer._js_mode == AssetMode.NONE


def test_reactive_partial_render_suppresses_assets():
    from tests.reactive_test_support import reactive_client, record_mutation

    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    with reactive_client(manifest):
        record_mutation("todos")
        rendered = str(ReactiveCounter.render())

    assert "<style>" not in rendered
    assert "<script" not in rendered
    assert "<link" not in rendered
