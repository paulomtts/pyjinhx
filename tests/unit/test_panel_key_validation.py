import pytest

from pyjinhx.builtins import Panel, PanelTrigger


def test_panel_rejects_invalid_panel_key():
    with pytest.raises(ValueError, match="panel key"):
        Panel(id="r1", panels={"bad key": "x"})


def test_panel_trigger_rejects_invalid_panel_key():
    with pytest.raises(ValueError, match="panel key"):
        PanelTrigger(id="t1", panel_id="r1", panel="bad key", content="x")


def test_panel_render_smoke():
    html = str(
        Panel(
            id="r-smoke",
            panels={"a": "<p>One</p>", "b": "<p>Two</p>"},
        ).render()
    )
    assert 'class="px-panel"' in html
    assert 'data-px-panel-key="a"' in html
    assert 'id="r-smoke-panel-a"' in html


def test_panel_trigger_render_smoke():
    html = str(
        PanelTrigger(id="t-smoke", panel_id="r-smoke", panel="a", content="Go").render()
    )
    assert 'class="px-panel-trigger"' in html
    assert 'data-px-panel-id="r-smoke"' in html
    assert 'aria-controls="r-smoke-panel-a"' in html
    assert "<button" not in html.lower()
