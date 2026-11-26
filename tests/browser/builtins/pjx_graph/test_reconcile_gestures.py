"""Browser tests for pjx_graph's updates held during a gesture, plus
hidden or resized nodes, root swaps and panel history after one."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pyjinhx.builtins.pjx_graph_side_panel import PJXGraphSidePanel
from tests.browser.builtins.pjx_graph._reconcile_helpers import (
    FIRED_BY,
    NESTED_CSS,
    _append,
    _call,
    _center,
    _drag,
    _edge,
    _events,
    _fanned,
    _flushed_once,
    _forget,
    _frames,
    _held,
    _html,
    _keyed,
    _layer,
    _mutate,
    _nested,
    _node,
    _numbers,
    _path,
    _plane,
    _port,
    _position,
    _press,
    _record,
    _remove,
    _rendered,
    _replace,
    _serve,
    _set,
    _settle,
    _span,
    _stage,
    _title,
    _trio,
    _visible,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page


# Ends the mouse's press the way a browser that takes the pointer over would.
CANCEL = """() => window.dispatchEvent(new PointerEvent('pointercancel',
    { pointerId: 1, bubbles: true }))"""


def _second_pointer(page: Page, kind: str) -> None:
    """Press pointer 2 on a's ok port ("pointerdown") or let it go ("pointerup")."""
    page.evaluate(
        """kind => {
            const target = kind === 'pointerdown'
                ? document.querySelector('#g-a [data-pjx-graph-port="out"][data-port="ok"]')
                : window;
            target.dispatchEvent(new PointerEvent(kind,
                { pointerId: 2, button: 0, bubbles: true }));
        }""",
        kind,
    )


# Found in review


def _edge_count(page: Page) -> int:
    return page.evaluate(
        "() => document.querySelectorAll('#g svg.pjx-graph__edge-plane path').length"
    )


# Holding updates during a gesture


def test_a_node_replacement_mid_drag_is_placed_only_after_release(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    bx, by = _center(page, _title("g-b"))
    _drag(page, (bx, by), (bx + 60, by + 40))
    assert _position(page, "g-b") == ["460px", "80px"]
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    edge = _path(page, "e1")
    before = _rendered(page)
    same = _html(session, _node("b", 400, 40, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", same))
    _held(page, before)
    # The swapped-in element shows the server position it was rendered with
    # (the component renders floats, so "400.0px", not the engine's "400px").
    assert _position(page, "g-b") == ["400.0px", "40.0px"]
    assert _path(page, "e1") == edge
    page.mouse.up()
    _flushed_once(page, before)
    assert _position(page, "g-b") == ["460px", "80px"]
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


def test_an_edge_added_mid_drag_is_drawn_only_after_release(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    # Drawn at the drag's last move; the pointer stays put once e3 is added.
    plain = _path(page, "e1")
    before = _rendered(page)
    _mutate(page, _append("#g-edges", _span(_edge("e3", "a", "b", port="ok"))))
    _held(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    page.mouse.up()
    _flushed_once(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    _fanned(page, "e1", "e3", plain)
    assert page_errors == []


def test_a_node_and_an_edge_change_mid_drag_flush_one_rendered(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    e2 = _path(page, "e2")
    before = _rendered(page)
    # Separate tasks, so the observer may reconcile between any two of them.
    moved_c = _html(session, _node("c", 400, 200, in_port=True))
    _mutate(page, _replace("#g-c", moved_c))
    _mutate(page, _append("#g-edges", _span(_edge("e3", "a", "b", port="ok"))))
    _mutate(page, _set("#g-b", "data-x", "460"))
    _mutate(page, reconcile="g")
    _mutate(page, reconcile="g")
    _held(page, before)
    assert _position(page, "g-b") == ["400px", "40px"]
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert _path(page, "e2") == e2
    page.mouse.up()
    _flushed_once(page, before)
    assert _position(page, "g-b") == ["460px", "40px"]
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    for edge, node in (("e1", "b"), ("e2", "c"), ("e3", "b")):
        anchor = _call(page, "inAnchor", node)
        assert _numbers(_path(page, edge))[-2:] == pytest.approx(
            [anchor["x"], anchor["y"]], abs=0.01
        )
    assert page_errors == []


def test_a_press_without_a_drag_holds_and_flushes_once(page, page_errors, session):
    _serve(page, _keyed(session))
    page.mouse.move(*_center(page, _title("g-b")))
    page.mouse.down()
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])), reconcile="g")
    _held(page, before)
    page.mouse.up()
    _flushed_once(page, before)
    assert [e["detail"] for e in _events(page, "select")] == [{"id": "b"}]
    assert page_errors == []


def test_a_gesture_with_no_update_fires_no_rendered(page, page_errors, session):
    _serve(page, _keyed(session))
    before = _rendered(page)
    x, y = _center(page, _title("g-a"))
    _drag(page, (x, y), (x + 60, y + 40))
    _frames(page, 4)
    assert _rendered(page) == before
    assert [e["detail"] for e in _events(page, "move")] == [
        {"id": "a", "x": 80, "y": 80}
    ]
    assert page_errors == []


def test_a_held_stage_does_not_hold_a_nested_stage(page, page_errors, session):
    _serve(page, _nested(page, session), NESTED_CSS)
    # The outer node's own title, not one of the nested stage's.
    x, y = _center(page, "#g-a > .pjx-graph__node-body > .pjx-graph__node-title")
    _press(page, (x, y), (x + 60, y + 40))
    inner, outer = _rendered(page, "in"), _rendered(page, "g")
    moved = _html(session, _node("y", 300, 60, "in", in_port=True))
    _mutate(page, _replace("#in-y", moved))
    assert _settle(page, inner, "in") == inner + 1
    _held(page, outer, "g")
    anchor = _call(page, "inAnchor", "y", stage_id="in")
    assert _numbers(_path(page, "i1", "in"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    page.mouse.up()
    _flushed_once(page, outer, "g")
    assert _rendered(page, "in") == inner + 1
    assert page_errors == []


def test_a_cancelled_drag_flushes_once(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])))
    _held(page, before)
    page.evaluate(CANCEL)
    _flushed_once(page, before)
    assert _events(page, "move") == []
    assert _position(page, "g-a") == ["20px", "40px"]
    page.mouse.up()
    assert _events(page, "move") == []
    assert page_errors == []


def test_reconcile_after_a_flushed_gesture_runs_normally(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])), reconcile="g")
    _held(page, before)
    page.mouse.up()
    after = _flushed_once(page, before)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])))
    assert _settle(page, after) == after + 1
    assert page.evaluate(FIRED_BY, ["g", "reconcile"]) == ["rendered"]
    assert page_errors == []


def test_replacing_the_pressed_node_mid_drag_places_the_replacement_at_the_drop(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    before = _rendered(page)
    _mutate(page, _replace("#g-a", _html(session, _trio()[0])))
    _held(page, before)
    page.mouse.up()
    _flushed_once(page, before)
    assert [e["detail"] for e in _events(page, "move")] == [
        {"id": "a", "x": 80, "y": 80}
    ]
    assert _record(page)["nodes"] == {
        "a": {"x": 80, "y": 80, "base": {"x": 20, "y": 40}}
    }
    assert _position(page, "g-a") == ["80px", "80px"]
    assert page_errors == []


def test_a_ctrl_press_on_a_node_holds_nothing(page, page_errors, session):
    _serve(page, _keyed(session))
    page.mouse.move(*_center(page, _title("g-b")))
    page.keyboard.down("Control")
    page.mouse.down()
    assert page.evaluate(FIRED_BY, ["g", "reconcile"]) == ["rendered"]
    page.mouse.up()
    page.keyboard.up("Control")
    assert page_errors == []


def test_draw_edges_during_a_drag_is_not_held(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    assert page.evaluate(FIRED_BY, ["g", "drawEdges"]) == ["rendered"]
    after = _rendered(page)
    page.mouse.up()
    _frames(page, 4)
    assert _rendered(page) == after
    assert page_errors == []


def test_a_background_pan_holds_nothing(page, page_errors, session):
    _serve(page, _keyed(session, edges=[]))
    box = page.locator("#g > .pjx-graph__canvas").bounding_box()
    assert box is not None
    # Empty canvas at identity: below node a, left of b and c.
    x, y = round(box["x"] + 150), round(box["y"] + 300)
    _press(page, (x, y), (x + 40, y + 20))
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])))
    assert _settle(page, before) == before + 1
    page.mouse.up()
    assert _events(page, "move") == []
    assert page_errors == []


def test_a_wire_drag_survives_a_node_layer_swap(page, page_errors, session):
    _serve(page, _keyed(session))
    x, y = _center(page, _port("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    before = _rendered(page)
    _mutate(page, _replace("#g-nodes", _html(session, _layer(session, _trio()))))
    _held(page, before)
    page.mouse.move(*_center(page, _title("g-c")), steps=2)
    page.mouse.up()
    assert [e["detail"] for e in _events(page, "wire")] == [
        {"from": "a", "port": "ok", "to": "c", "kind": "", "to_port": ""}
    ]
    _flushed_once(page, before)
    assert page_errors == []


def test_a_wire_whose_source_is_removed_mid_drag_fires_no_wire_and_flushes_once(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    x, y = _center(page, _port("g-a"))
    target = _center(page, _title("g-c"))
    _press(page, (x, y), (x + 60, y + 40))
    before = _rendered(page)
    _mutate(page, _remove("#g-a"))
    _held(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    page.mouse.move(*target, steps=2)
    page.mouse.up()
    assert _events(page, "wire") == []
    _flushed_once(page, before)
    # Both edges start at a, so with a gone none is drawn.
    assert _visible(page) == []
    assert page_errors == []


def test_overlapping_gestures_flush_once_when_the_last_ends(page, page_errors, session):
    _serve(page, _keyed(session))
    _second_pointer(page, "pointerdown")
    x, y = _center(page, _title("g-b"))
    _press(page, (x, y), (x + 60, y + 40))
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])), reconcile="g")
    page.mouse.up()
    # The wire's pointer is still down, so the node's release flushes nothing.
    _held(page, before)
    assert [e["detail"] for e in _events(page, "move")] == [
        {"id": "b", "x": 460, "y": 80}
    ]
    _second_pointer(page, "pointerup")
    _flushed_once(page, before)
    assert _events(page, "wire") == []
    assert page_errors == []


def test_a_pointerup_stopped_inside_a_node_does_not_wedge_the_stage(
    page, page_errors, session
):
    _serve(page, _stage(session), record="")
    page.evaluate(
        """() => document.querySelector('#g-a .pjx-graph__node-title')
            .addEventListener('pointerup', (e) => e.stopPropagation())"""
    )
    x, y = _center(page, _title("g-a"))
    _drag(page, (x, y), (x + 60, y + 40))
    _mutate(page, _set("#g-b", "data-x", "410"), reconcile="g")
    assert _position(page, "g-b") == ["410px", "40px"]
    assert page_errors == []


def test_a_stage_that_mounted_hidden_is_framed_and_drawn_when_shown(
    page, page_errors, session
):
    stage = _stage(session)
    _serve(page, f'<div id="wrap" style="display:none">{stage}</div>')
    assert _edge_count(page) == 0
    page.evaluate("() => { document.getElementById('wrap').style.display = 'block'; }")
    page.wait_for_function(
        "() => document.querySelectorAll('#g svg.pjx-graph__edge-plane path').length > 0"
    )
    assert page_errors == []


def test_edges_follow_a_node_that_changes_size_without_a_swap(
    page, page_errors, session
):
    _serve(page, _stage(session), record="")
    before = [el["d"] for el in _plane(page)]
    page.evaluate("() => { document.getElementById('g-b').style.minHeight = '300px'; }")
    page.wait_for_function(
        """before => Array.from(document.querySelectorAll(
            '#g svg.pjx-graph__edge-plane path')).map(p => p.getAttribute('d'))
            .join('|') !== before.join('|')""",
        arg=before,
    )
    assert page_errors == []


def test_a_hidden_node_disappears(page, page_errors, session):
    _serve(page, _stage(session), record="")
    page.evaluate("() => { document.getElementById('g-b').hidden = true; }")
    assert not page.locator("#g-b").is_visible()
    assert page_errors == []


def test_swapping_the_roots_inner_markup_remounts_the_stage(page, page_errors, session):
    _serve(page, _stage(session), record="")
    before = _edge_count(page)
    assert before > 0
    page.evaluate(
        """() => {
            const root = document.getElementById('g');
            // Server markup has an empty plane; drawn paths are the engine's.
            const copy = root.cloneNode(true);
            copy.querySelector('svg.pjx-graph__edge-plane').replaceChildren();
            root.innerHTML = copy.innerHTML;
        }"""
    )
    page.wait_for_function(
        "n => document.querySelectorAll('#g svg.pjx-graph__edge-plane path').length === n",
        arg=before,
    )
    _forget(page)
    page.mouse.click(*_center(page, _title("g-a")))
    assert [e["type"] for e in _events(page, "select")] == ["select"]
    assert page_errors == []


def test_a_settle_inside_a_node_keeps_an_unkeyed_drop(page, page_errors, session):
    _serve(page, _stage(session), record="")
    x, y = _center(page, _title("g-a"))
    _drag(page, (x, y), (x + 60, y + 40))
    dropped = _position(page, "g-a")
    page.evaluate(
        """() => document.querySelector('#g-a .pjx-graph__node-title')
            .dispatchEvent(new CustomEvent('htmx:afterSettle', { bubbles: true }))"""
    )
    _frames(page)
    assert _position(page, "g-a") == dropped
    assert page_errors == []


def test_a_swapped_closed_panel_forgets_the_panel_history(page, page_errors, session):
    panel = PJXGraphSidePanel(id="g-panel", title="Details")
    _serve(page, _stage(session, panel=panel), record="")
    page.evaluate("() => { pjx.graph.panel.open(document.getElementById('g'), 'a'); }")
    page.evaluate("() => { pjx.graph.panel.open(document.getElementById('g'), 'b'); }")
    closed = _html(session, PJXGraphSidePanel(id="g-panel", title="Details"))
    page.evaluate(
        """html => {
            document.getElementById('g-panel').outerHTML = html;
            document.getElementById('g-panel')
                .dispatchEvent(new CustomEvent('htmx:afterSettle', { bubbles: true }));
        }""",
        closed,
    )
    page.evaluate("() => { pjx.graph.panel.open(document.getElementById('g'), 'c'); }")
    assert page.evaluate(
        "() => document.querySelector('#g [data-pjx-graph-panel-back]').hidden"
    )
    assert page_errors == []
