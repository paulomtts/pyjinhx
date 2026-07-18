"""Browser contracts for PJXTabList(reorderable=True)."""
import pytest

pytest.importorskip("playwright")

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]


def _order(page):
    return page.eval_on_selector_all(
        "#rx-reorder-tabs [data-pjx-tab]", "els => els.map(e => e.id)"
    )


def test_ctrl_arrow_right_moves_tab_forward(sink_page):
    assert _order(sink_page) == ["rx-reorder-a", "rx-reorder-b", "rx-reorder-c"]
    sink_page.focus("#rx-reorder-a")
    sink_page.keyboard.down("Control")
    sink_page.keyboard.press("ArrowRight")
    sink_page.keyboard.up("Control")
    assert _order(sink_page) == ["rx-reorder-b", "rx-reorder-a", "rx-reorder-c"]
    assert sink_page.evaluate("document.activeElement.id") == "rx-reorder-a"


def test_ctrl_arrow_left_moves_tab_backward(sink_page):
    sink_page.focus("#rx-reorder-c")
    sink_page.keyboard.down("Control")
    sink_page.keyboard.press("ArrowLeft")
    sink_page.keyboard.up("Control")
    assert _order(sink_page) == ["rx-reorder-a", "rx-reorder-c", "rx-reorder-b"]


def test_reorder_fires_cancelable_event(sink_page):
    sink_page.evaluate(
        "document.getElementById('rx-reorder-tabs')"
        ".addEventListener('pjx:tab:before-reorder', e => e.preventDefault(), {once:true})"
    )
    sink_page.focus("#rx-reorder-a")
    sink_page.keyboard.down("Control")
    sink_page.keyboard.press("ArrowRight")
    sink_page.keyboard.up("Control")
    assert _order(sink_page) == ["rx-reorder-a", "rx-reorder-b", "rx-reorder-c"]


def test_plain_arrow_still_roves_focus_not_reorders(sink_page):
    sink_page.focus("#rx-reorder-a")
    sink_page.keyboard.press("ArrowRight")
    assert _order(sink_page) == ["rx-reorder-a", "rx-reorder-b", "rx-reorder-c"]
    assert sink_page.evaluate("document.activeElement.id") == "rx-reorder-b"
