"""Browser tests for pjx_graph's interaction after swaps, edge changes and node lookup."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from pyjinhx.builtins.pjx_graph_edges import PJXGraphEdges
from tests.browser.builtins.pjx_graph._reconcile_helpers import (
    EDGES,
    FIRED_BY,
    IDENTITY_VIEW,
    NESTED_CSS,
    RECONCILE,
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


# Each label in a stage's own plane as [edge id, shown text], in DOM order.
LABELS = """id => {
    const plane = document.querySelector('#' + id
        + ' > .pjx-graph__canvas > .pjx-graph__viewport > svg.pjx-graph__edge-plane');
    return Array.from(plane.querySelectorAll('.pjx-graph__edge-label'))
        .map(t => [t.getAttribute('data-edge-id'), t.textContent]);
}"""


# Calls drawEdges once and counts the viewport's node queries it makes.
COUNT_NODE_QUERIES = """id => {
    const viewport = document.querySelector('#' + id + ' > .pjx-graph__canvas > .pjx-graph__viewport');
    let count = 0;
    viewport.querySelectorAll = function (selector) {
        if (selector === '[data-node-id]') count += 1;
        return Element.prototype.querySelectorAll.call(this, selector);
    };
    try {
        pjx.graph.get(document.getElementById(id)).drawEdges();
    } finally {
        delete viewport.querySelectorAll;
    }
    return count;
}"""


def _edge_span(edge_id: str, stage_id: str = "g") -> str:
    return f'#{stage_id}-edges [data-edge-id="{edge_id}"]'


def _labels(page: Page, stage_id: str = "g") -> list[list[str]]:
    return page.evaluate(LABELS, stage_id)


def _fan(page: Page) -> tuple[str, int]:
    """Add e3 beside e1 (a→b on ok); return e1's lone path and the settled rendered count."""
    plain = _path(page, "e1")
    before = _rendered(page)
    _mutate(page, _append("#g-edges", _span(_edge("e3", "a", "b", port="ok"))))
    return plain, _settle(page, before)


# Interaction after swaps


def test_handlers_are_not_double_bound_after_swaps(page, page_errors, session):
    _serve(page, _keyed(session))
    for b in [(400, 40), (400, 40)]:
        before = _rendered(page)
        _mutate(page, _replace("#g-nodes", _html(session, _layer(session, _trio(b=b)))))
        _settle(page, before)
    for _ in range(3):
        page.evaluate(RECONCILE, "g")
    _forget(page)
    page.click(_title("g-b"))
    assert [e["type"] for e in _events(page, "before-select", "select")] == [
        "before-select",
        "select",
    ]
    _forget(page)
    x, y = _center(page, _title("g-b"))
    _drag(page, (x, y), (x + 60, y + 40))
    assert [e["detail"] for e in _events(page, "move")] == [
        {"id": "b", "x": 460, "y": 80}
    ]
    assert page_errors == []


def test_a_wire_from_a_replaced_node_fires_one_wire_event(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(page, _replace("#g-a", _html(session, _trio()[0])))
    _settle(page, before)
    _forget(page)
    _drag(page, _center(page, _port("g-a")), _center(page, _title("g-c")))
    assert [e["detail"] for e in _events(page, "wire")] == [
        {"from": "a", "port": "ok", "to": "c", "kind": "", "to_port": ""}
    ]
    assert page_errors == []


def test_a_replaced_selected_node_stays_selected(page, page_errors, session):
    _serve(page, _stage(session))
    page.click(_title("g-b"))
    _forget(page)
    before = _rendered(page)
    _mutate(page, _replace("#g-b", _html(session, _trio()[1])))
    _settle(page, before)
    assert page.evaluate(
        "() => document.getElementById('g-b').classList.contains('pjx-graph__node--selected')"
    )
    assert _events(page, "deselect") == []
    assert page_errors == []


def test_a_reconcile_during_a_node_drag_leaves_the_dragged_node_alone(
    page, page_errors, session
):
    _serve(page, _keyed(session))
    x, y = _center(page, _title("g-a"))
    _press(page, (x, y), (x + 60, y + 40))
    assert _position(page, "g-a") == ["80px", "80px"]
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])), reconcile="g")
    assert page.evaluate(FIRED_BY, ["g", "reconcile"]) == []
    _held(page, before)
    assert _position(page, "g-a") == ["80px", "80px"]
    page.mouse.up()
    _flushed_once(page, before)
    assert [e["detail"] for e in _events(page, "move")] == [
        {"id": "a", "x": 80, "y": 80}
    ]
    assert _position(page, "g-a") == ["80px", "80px"]
    assert page_errors == []


# Edge changes


def test_adding_one_edge_fans_the_pair(page, page_errors, session):
    _serve(page, _stage(session))
    plain = _path(page, "e1")
    before = _rendered(page)
    _mutate(page, _append("#g-edges", _span(_edge("e3", "a", "b", port="ok"))))
    assert _settle(page, before) == before + 1
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    _fanned(page, "e1", "e3", plain)
    assert page_errors == []


def test_removing_one_edge_unfans_the_pair(page, page_errors, session):
    _serve(page, _stage(session))
    plain, before = _fan(page)
    _mutate(page, _remove(_edge_span("e3")))
    assert _settle(page, before) == before + 1
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert _path(page, "e1") == plain
    assert page_errors == []


def test_swapping_the_whole_edges_element_draws_only_the_new_list(
    page, page_errors, session
):
    _serve(page, _stage(session))
    plain = _path(page, "e1")
    before = _rendered(page)
    fresh = [
        _edge("e1", "a", "b", port="ok", state="ok"),
        _edge("e3", "a", "b", port="ok"),
        _edge("e4", "b", "c", port="ok", state="fail"),
    ]
    _mutate(
        page,
        _replace("#g-edges", _html(session, PJXGraphEdges(id="g-edges", edges=fresh))),
    )
    assert _settle(page, before) == before + 1
    visible = _visible(page)
    assert [e["edge"] for e in visible] == ["e1", "e3", "e4"]
    assert [e["state"] for e in visible] == ["ok", "", "fail"]
    assert "e2" not in {el["edge"] for el in _plane(page)}
    _fanned(page, "e1", "e3", plain)
    assert page_errors == []


def test_changing_an_edge_state_restyles_it_and_keeps_the_fan(
    page, page_errors, session
):
    edges = [_edge("e1", "a", "b", port="ok", state="ok"), EDGES[1]]
    _serve(page, _stage(session, edges=edges))
    plain, before = _fan(page)
    _mutate(page, _set(_edge_span("e1"), "data-state", "fail"))
    assert _settle(page, before) == before + 1
    e1 = next(el for el in _visible(page) if el["edge"] == "e1")
    assert e1["cls"].split() == ["pjx-graph__edge", "pjx-graph__edge--fail"]
    assert e1["state"] == "fail"
    _fanned(page, "e1", "e3", plain)
    # A state with whitespace is still the app's word, but no class.
    _mutate(page, _set(_edge_span("e1"), "data-state", "is late"))
    _settle(page, before + 1)
    e1 = next(el for el in _visible(page) if el["edge"] == "e1")
    assert e1["cls"] == "pjx-graph__edge"
    assert e1["state"] == "is late"
    assert page_errors == []


def test_changing_edge_attributes_in_one_task_causes_one_reconcile(
    page, page_errors, session
):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(
        page,
        _set(_edge_span("e1"), "data-state", "fail"),
        _set(_edge_span("e1"), "data-label", "retry"),
        _set(_edge_span("e2"), "data-port", "ok"),
        _append("#g-edges", _span(_edge("e3", "b", "c", port="ok"))),
    )
    assert _settle(page, before) == before + 1
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    assert _labels(page) == [["e1", "retry"]]
    assert page_errors == []


def test_retargeting_an_edge_moves_it_between_pairs(page, page_errors, session):
    _serve(page, _stage(session))
    plain, before = _fan(page)
    e2_before = _path(page, "e2")
    _mutate(page, _set(_edge_span("e3"), "data-to", "c"))
    _settle(page, before)
    # a→b is down to e1 again, and a→c now holds e2 and e3, so it fans.
    assert _path(page, "e1") == plain
    assert _path(page, "e2") != e2_before
    e3 = next(el for el in _visible(page) if el["edge"] == "e3")
    assert e3["to"] == "c"
    anchor = _call(page, "inAnchor", "c")
    assert _numbers(e3["d"])[-2:] == pytest.approx([anchor["x"], anchor["y"]], abs=0.01)
    assert page_errors == []


def test_changing_an_edge_port_moves_its_start(page, page_errors, session):
    _serve(page, _stage(session))
    start = _numbers(_path(page, "e1"))[:2]
    before = _rendered(page)
    _mutate(page, _set(_edge_span("e1"), "data-port", "fail"))
    _settle(page, before)
    moved = _numbers(_path(page, "e1"))[:2]
    anchor = _call(page, "outAnchor", "a", "fail")
    assert moved == pytest.approx([anchor["x"], anchor["y"]], abs=0.01)
    assert moved != pytest.approx(start, abs=0.01)
    assert page_errors == []


def test_changing_an_edge_label_rewrites_and_removes_it(page, page_errors, session):
    _serve(page, _stage(session))
    assert _labels(page) == []
    before = _rendered(page)
    _mutate(page, _set(_edge_span("e1"), "data-label", "go"))
    before = _settle(page, before)
    assert _labels(page) == [["e1", "go"]]
    _mutate(page, _set(_edge_span("e1"), "data-label", ""))
    _settle(page, before)
    assert _labels(page) == []
    assert page_errors == []


def test_retargeting_an_edge_to_an_unknown_node_hides_it(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(page, _set(_edge_span("e1"), "data-to", "zz"))
    before = _settle(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e2"]
    _mutate(
        page,
        f"document.querySelector({json.dumps(_edge_span('e2'))})"
        ".removeAttribute('data-from');",
    )
    _settle(page, before)
    assert _visible(page) == []
    assert page_errors == []


def test_an_unwatched_attribute_schedules_nothing(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(
        page,
        "document.getElementById('g-a').classList.add('app-flagged');",
        "document.getElementById('g-c').style.outline = '1px solid red';",
        _set("#g-b", "data-node-type", "task"),
        _set(_edge_span("e1"), "title", "first"),
        # The app's own markup inside a node, not one of the graph's elements.
        _set(_title("g-a"), "data-state", "busy"),
    )
    _frames(page, 4)
    assert _rendered(page) == before
    assert page_errors == []


def test_an_attribute_reconcile_does_not_trigger_another(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(page, _set(_edge_span("e1"), "data-state", "fail"))
    after = _settle(page, before)
    assert after == before + 1
    _frames(page, 4)
    assert _rendered(page) == after
    assert page_errors == []


def test_an_edge_state_edit_inside_a_nested_stage_settles(page, page_errors, session):
    _serve(page, _nested(page, session), NESTED_CSS)
    inner, outer = _rendered(page, "in"), _rendered(page, "g")
    _mutate(page, _set(_edge_span("i1", "in"), "data-state", "fail"))
    _settle(page, inner, "in")
    counts = (_rendered(page, "in"), _rendered(page, "g"))
    assert counts[0] == inner + 1
    assert counts[1] <= outer + 1
    _frames(page, 4)
    assert (_rendered(page, "in"), _rendered(page, "g")) == counts
    i1 = next(el for el in _visible(page, "in") if el["edge"] == "i1")
    assert i1["cls"].split() == ["pjx-graph__edge", "pjx-graph__edge--fail"]
    assert page_errors == []


def test_changing_a_kept_nodes_data_x_moves_it_and_its_edges(
    page, page_errors, session
):
    _serve(page, _stage(session))
    edge = _path(page, "e1")
    before = _rendered(page)
    _mutate(page, _set("#g-b", "data-x", "460"))
    _settle(page, before)
    assert _position(page, "g-b") == ["460px", "40px"]
    assert _path(page, "e1") != edge
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


def test_a_new_server_position_on_a_kept_node_discards_its_drop(
    page, page_errors, session
):
    record = {
        "view": IDENTITY_VIEW,
        "nodes": {"b": {"x": 300, "y": 150, "base": {"x": 400, "y": 40}}},
    }
    _serve(page, _keyed(session), record=record)
    assert _position(page, "g-b") == ["300px", "150px"]
    before = _rendered(page)
    _mutate(page, _set("#g-b", "data-y", "90"))
    _settle(page, before)
    assert _position(page, "g-b") == ["400px", "90px"]
    assert _record(page) == {"view": IDENTITY_VIEW, "nodes": {}}
    assert page_errors == []


def test_a_direct_reconcile_after_set_attribute_places_the_node(
    page, page_errors, session
):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(page, _set("#g-b", "data-x", "460"), reconcile="g")
    assert _position(page, "g-b") == ["460px", "40px"]
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    # The observer's own reconcile still follows, and moves nothing again.
    _settle(page, before + 1)
    assert _position(page, "g-b") == ["460px", "40px"]
    assert page_errors == []


def test_a_blank_data_x_keeps_the_node_where_it_was(page, page_errors, session):
    _serve(page, _stage(session))
    for value in ("", "left"):
        before = _rendered(page)
        _mutate(page, _set("#g-b", "data-x", value))
        _settle(page, before)
        assert _position(page, "g-b") == ["400px", "40px"]
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert page_errors == []


def test_resending_the_same_position_keeps_a_dropped_node_where_it_was_dropped(
    page, page_errors, session
):
    # No storage key: the drop lives only in the node's style.
    _serve(page, _stage(session), record="")
    x, y = _center(page, _title("g-a"))
    _drag(page, (x, y), (x + 60, y + 40))
    dropped = _position(page, "g-a")
    assert dropped != ["20px", "40px"]
    before = _rendered(page)
    # A morphing swap writes the attributes back even when they are unchanged.
    _mutate(
        page,
        """for (const name of ['data-x', 'data-y']) {
            const node = document.getElementById('g-a');
            node.setAttribute(name, node.getAttribute(name));
        }""",
    )
    _settle(page, before)
    assert _position(page, "g-a") == dropped
    assert page_errors == []


def test_moving_a_nested_stages_node_by_attribute_settles(page, page_errors, session):
    _serve(page, _nested(page, session), NESTED_CSS)
    inner, outer = _rendered(page, "in"), _rendered(page, "g")
    _mutate(page, _set("#in-y", "data-y", "60"))
    _settle(page, inner, "in")
    counts = (_rendered(page, "in"), _rendered(page, "g"))
    assert counts[0] == inner + 1
    assert counts[1] <= outer + 1
    _frames(page, 4)
    assert (_rendered(page, "in"), _rendered(page, "g")) == counts
    assert _position(page, "in-y") == ["300px", "60px"]
    anchor = _call(page, "inAnchor", "y", stage_id="in")
    assert _numbers(_path(page, "i1", "in"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


# Node lookup


def test_a_redraw_queries_nodes_once(page, page_errors, session):
    edges = [_edge(f"e{i}", "a", "b", port="ok") for i in range(5)] + [
        _edge(f"e{i}", "a", "c", port="fail") for i in range(5, 10)
    ]
    _serve(page, _stage(session, edges=edges))
    assert len(_visible(page)) == 10
    assert page.evaluate(COUNT_NODE_QUERIES, "g") == 1
    assert len(_visible(page)) == 10
    assert page_errors == []


def test_lookups_outside_a_redraw_see_a_node_added_in_the_same_task(
    page, page_errors, session
):
    _serve(page, _stage(session))
    added = _html(session, _node("d", 700, 40, in_port=True))
    found = page.evaluate(
        """html => {
            document.getElementById('g-nodes').insertAdjacentHTML('beforeend', html);
            const instance = pjx.graph.get(document.getElementById('g'));
            return [instance.box('d') !== null, instance.select('d')];
        }""",
        added,
    )
    assert found == [True, True]
    assert page_errors == []
