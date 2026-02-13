import logging

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


def test_missing_extra_js_file_warns(caplog):
    component = UnifiedComponent(
        id="missing-js-1",
        text="Test",
        js=["tests/ui/nonexistent.js"],
    )

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        rendered = component.render()

    assert "<div" in str(rendered)
    assert "missing-js-1" in str(rendered)
    assert "console.log('Button loaded');" in str(rendered)
    assert "nonexistent" not in str(rendered)
    assert any("nonexistent.js" in record.message for record in caplog.records)


def test_missing_extra_css_file_warns(caplog):
    component = UnifiedComponent(
        id="missing-css-1",
        text="Test",
        css=["tests/ui/nonexistent.css"],
    )

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        rendered = component.render()

    assert "<div" in str(rendered)
    assert "nonexistent" not in str(rendered)
    assert any("nonexistent.css" in record.message for record in caplog.records)
