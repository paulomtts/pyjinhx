from tests.ui.no_js_component import NoJsComponent
from tests.ui.unified_component import UnifiedComponent


def test_missing_component_js_file_handles_gracefully():
    component = NoJsComponent(id="no-js-1", text="Test")

    rendered = component.render()

    assert (
        rendered
        == """<div id="no-js-1">Test</div>
"""
    )


def test_missing_extra_js_file_is_ignored():
    component = UnifiedComponent(
        id="missing-js-1",
        text="Test",
        js=["tests/ui/nonexistent.js"],
    )

    rendered = component.render()

    assert "<div" in str(rendered)
    assert "missing-js-1" in str(rendered)
    assert "console.log('Button loaded');" in str(rendered)
    assert "nonexistent" not in str(rendered)
