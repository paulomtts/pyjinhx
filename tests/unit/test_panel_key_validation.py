import pytest

from pyjinhx.builtins import PJXPanel, PJXPanelTrigger


def test_panel_rejects_invalid_panel_key():
    with pytest.raises(ValueError, match="panel key"):
        PJXPanel(id="r1", panels={"bad key": "x"})


def test_panel_trigger_rejects_invalid_panel_key():
    with pytest.raises(ValueError, match="panel key"):
        PJXPanelTrigger(id="t1", panel_id="r1", panel="bad key", content="x")


def test_panel_render_smoke():
    html = str(
        PJXPanel(
            id="r-smoke",
            panels={"a": "<p>One</p>", "b": "<p>Two</p>"},
        ).render()
    )
    assert 'class="pjx-panel"' in html
    assert 'data-pjx-panel-key="a"' in html
    assert 'id="r-smoke-panel-a"' in html


def test_panel_trigger_render_smoke():
    html = str(
        PJXPanelTrigger(id="t-smoke", panel_id="r-smoke", panel="a", content="Go").render()
    )
    assert 'class="pjx-panel-trigger"' in html
    assert 'data-pjx-panel-id="r-smoke"' in html
    assert 'aria-controls="r-smoke-panel-a"' in html
    assert "<button" not in html.lower()
