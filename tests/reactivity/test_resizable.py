"""Browser contracts for the PJXResizable* split pane."""
import pytest

pytest.importorskip("playwright")

pytestmark = [pytest.mark.pjx_runtime, pytest.mark.reactivity]


def _grow(page, el_id):
    return float(page.eval_on_selector(f"#{el_id}", "el => el.style.flexGrow"))


def _drag(page, handle_id, dx, dy=0):
    box = page.locator(f"#{handle_id}").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(cx, cy)
    page.mouse.down()
    page.mouse.move(cx + dx, cy + dy, steps=5)
    page.mouse.up()


def test_drag_trades_space_between_neighbors(sink_page):
    left0, right0 = _grow(sink_page, "rx-resize-left"), _grow(sink_page, "rx-resize-right")
    _drag(sink_page, "rx-resize-handle", 80)  # box is 400px wide → ~+20%
    left1, right1 = _grow(sink_page, "rx-resize-left"), _grow(sink_page, "rx-resize-right")
    assert left1 > left0 + 10
    assert right1 < right0 - 10
    assert abs((left1 + right1) - (left0 + right0)) < 0.5  # sum preserved


def test_min_clamps_the_drag(sink_page):
    _drag(sink_page, "rx-resize-handle", -400)  # drag far left; left has min=20
    assert _grow(sink_page, "rx-resize-left") >= 19.5


def test_resize_event_fires_with_sizes(sink_page):
    sink_page.evaluate(
        "window.__rs = null;"
        "document.getElementById('rx-resize-group')"
        ".addEventListener('pjx:resize', e => { window.__rs = e.detail.sizes; })"
    )
    _drag(sink_page, "rx-resize-handle", 40)
    sizes = sink_page.evaluate("window.__rs")
    assert isinstance(sizes, list) and len(sizes) == 2


def test_keyboard_resizes(sink_page):
    left0 = _grow(sink_page, "rx-resize-left")
    sink_page.focus("#rx-resize-handle")
    sink_page.keyboard.press("ArrowRight")
    assert _grow(sink_page, "rx-resize-left") > left0
