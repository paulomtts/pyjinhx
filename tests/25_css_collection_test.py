from pyjinhx import Renderer
from tests.ui.unified_component import UnifiedComponent


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
    component = UnifiedComponent(
        id="css-parent-1", title="Parent", items=[nested]
    )

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


def test_missing_extra_css_ignored():
    component = UnifiedComponent(
        id="css-missing-1",
        text="Missing",
        css=["tests/ui/nonexistent.css"],
    )

    rendered = str(component.render())

    assert "<div" in rendered
    assert "nonexistent" not in rendered


def test_inline_css_false_disables_injection():
    renderer = Renderer.get_default_renderer(inline_css=False)
    component = UnifiedComponent(id="css-off-1", text="No CSS")

    rendered = str(
        component._render(_renderer=renderer)
    )

    assert "<style>" not in rendered


def test_css_order_styles_before_scripts():
    component = UnifiedComponent(id="css-order-1", text="Order Test")

    rendered = str(component.render())

    style_pos = rendered.find("<style>")
    script_pos = rendered.find("<script>")
    assert style_pos < script_pos, "Styles should come before scripts"
