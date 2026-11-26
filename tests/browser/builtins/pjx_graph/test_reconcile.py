"""Browser tests for pjx_graph's reconcile call, stored positions, swaps and coalescing."""

from __future__ import annotations

import json

import pytest

from pyjinhx.builtins.pjx_graph_node import PJXGraphNode
from tests.browser.builtins.pjx_graph._reconcile_helpers import (
    EDGES,
    IDENTITY_VIEW,
    NESTED_CSS,
    RECONCILE,
    _append,
    _call,
    _center,
    _drag,
    _edge,
    _events,
    _forget,
    _frames,
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
    _raw,
    _record,
    _remove,
    _rendered,
    _replace,
    _serve,
    _settle,
    _span,
    _stage,
    _title,
    _trio,
    _visible,
)

# Calling reconcile


def test_get_exposes_reconcile_and_it_fires_one_rendered(page, page_errors, session):
    _serve(page, _stage(session))
    _forget(page)
    assert (
        page.evaluate(
            "() => typeof pjx.graph.get(document.getElementById('g')).reconcile"
        )
        == "function"
    )
    assert page.evaluate(RECONCILE, "g") == "undefined"
    assert _events(page, "rendered") == [
        {"type": "rendered", "detail": None, "target": "g", "cancelable": False}
    ]
    assert page_errors == []


def test_mount_still_returns_the_same_instance(page, page_errors, session):
    _serve(page, _stage(session))
    same = page.evaluate(
        """() => { const root = document.getElementById('g');
            return pjx.graph.mount(root) === pjx.graph.get(root); }"""
    )
    assert same is True
    keys = page.evaluate(
        "() => Object.keys(pjx.graph.get(document.getElementById('g'))).sort()"
    )
    assert keys == sorted(
        [
            "root",
            "box",
            "inAnchor",
            "outAnchor",
            "fit",
            "zoomBy",
            "drawEdges",
            "select",
            "deselect",
            "reconcile",
        ]
    )
    assert page_errors == []


def test_reconcile_twice_draws_the_same_edges(page, page_errors, session):
    _serve(page, _stage(session))
    page.evaluate(RECONCILE, "g")
    once = _plane(page)
    _forget(page)
    for _ in range(3):
        page.evaluate(RECONCILE, "g")
    assert _plane(page) == once
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert len(_events(page, "rendered")) == 3
    assert page_errors == []


def test_reconcile_after_a_replaced_node_redraws_its_edge_at_the_new_anchor(
    page, page_errors, session
):
    _serve(page, _stage(session))
    moved = _html(session, _node("b", 400, 120, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", moved), reconcile="g")
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert _position(page, "g-b") == ["400px", "120px"]
    assert page_errors == []


def test_reconcile_with_an_empty_node_layer_draws_nothing(page, page_errors, session):
    _serve(page, _stage(session))
    # Counted inside the same task, before any frame could add an observer's reconcile.
    fired = page.evaluate(
        """() => { const from = window.__events.length;
            document.getElementById('g-nodes').replaceChildren();
            pjx.graph.get(document.getElementById('g')).reconcile();
            return window.__events.slice(from).map((e) => e.type); }"""
    )
    assert fired == ["rendered"]
    assert _visible(page) == []
    assert page_errors == []


# Positions


def test_a_replaced_node_takes_its_stored_drop_while_the_server_position_is_unchanged(
    page, page_errors, session
):
    seeded = json.dumps(
        {
            "view": IDENTITY_VIEW,
            "nodes": {"b": {"x": 300, "y": 150, "base": {"x": 400, "y": 40}}},
        }
    )
    _serve(page, _keyed(session), record=seeded)
    assert _position(page, "g-b") == ["300px", "150px"]
    same = _html(session, _node("b", 400, 40, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", same), reconcile="g")
    assert _position(page, "g-b") == ["300px", "150px"]
    assert _raw(page) == seeded
    assert page_errors == []


def test_a_replaced_node_keeps_its_stored_drop_after_htmx_settles_the_swap(
    page, page_errors, session
):
    seeded = json.dumps(
        {
            "view": IDENTITY_VIEW,
            "nodes": {"b": {"x": 300, "y": 150, "base": {"x": 400, "y": 40}}},
        }
    )
    _serve(page, _keyed(session), record=seeded)
    same = _html(session, _node("b", 400, 40, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", same), reconcile="g")
    # htmx settles a swapped element by writing the server's style back, then
    # announces it; the drop has to survive that.
    page.evaluate(
        """() => {
            const node = document.getElementById('g-b');
            node.setAttribute('style', '--pjx-graph-node-x:400.0px;--pjx-graph-node-y:40.0px;');
            node.dispatchEvent(new CustomEvent('htmx:afterSettle', { bubbles: true }));
        }"""
    )
    assert _position(page, "g-b") == ["300px", "150px"]
    assert _raw(page) == seeded
    assert page_errors == []


def test_a_replaced_node_with_a_new_server_position_discards_the_drop(
    page, page_errors, session
):
    record = {
        "view": IDENTITY_VIEW,
        "nodes": {"b": {"x": 300, "y": 150, "base": {"x": 400, "y": 40}}},
    }
    _serve(page, _keyed(session), record=record)
    moved = _html(session, _node("b", 400, 90, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", moved), reconcile="g")
    assert _position(page, "g-b") == ["400px", "90px"]
    assert _record(page) == {"view": IDENTITY_VIEW, "nodes": {}}
    assert page_errors == []


def test_an_unrelated_swap_keeps_a_dropped_node_where_it_was_dropped(
    page, page_errors, session
):
    # No storage key: the drop lives only in the node's style.
    _serve(page, _stage(session), record="")
    x, y = _center(page, _title("g-a"))
    _drag(page, (x, y), (x + 60, y + 40))
    dropped = _position(page, "g-a")
    assert dropped != ["20px", "40px"]
    _mutate(page, _append("#g-edges", _span(_edge("e3", "b", "c"))), reconcile="g")
    assert _position(page, "g-a") == dropped
    assert page_errors == []


def test_a_duplicate_node_id_does_not_break_reconcile(page, page_errors, session):
    _serve(page, _keyed(session))
    duplicate = _html(
        session, PJXGraphNode(id="g-b2", node_id="b", x=600, y=260, title="B2")
    )
    page.evaluate(
        "() => document.getElementById('g-b').style.setProperty("
        "'--pjx-graph-node-x', '410px')"
    )
    _mutate(page, _append("#g-nodes", duplicate), reconcile="g")
    _mutate(page, reconcile="g")
    # The first b is kept, so its style is untouched; the duplicate is placed.
    assert _position(page, "g-b") == ["410px", "40px"]
    assert _position(page, "g-b2") == ["600px", "260px"]
    anchor = _call(page, "inAnchor", "b")
    # In world space: the viewport's client origin is not the page's.
    first = page.evaluate(
        """() => { const r = document.getElementById('g-b').getBoundingClientRect();
            const o = document.querySelector('#g .pjx-graph__viewport').getBoundingClientRect();
            return [r.left - o.left, r.top - o.top + r.height / 2]; }"""
    )
    assert [anchor["x"], anchor["y"]] == pytest.approx(first, abs=0.01)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert page_errors == []


# Noticing swaps


def test_replacing_the_whole_nodes_layer_redraws_edges_at_the_new_positions(
    page, page_errors, session
):
    _serve(page, _stage(session))
    before = _rendered(page)
    layer = _html(session, _layer(session, _trio(b=(400, 180))))
    _mutate(page, _replace("#g-nodes", layer))
    _settle(page, before)
    assert _position(page, "g-b") == ["400px", "180px"]
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert anchor["y"] > 180
    assert page_errors == []


def test_replacing_one_node_by_id_moves_only_that_node(page, page_errors, session):
    _serve(page, _stage(session))
    page.evaluate(
        "() => ['g-a', 'g-c'].forEach((id) => { document.getElementById(id).__kept = id; })"
    )
    before = _rendered(page)
    edge = _path(page, "e1")
    moved = _html(session, _node("b", 400, 140, in_port=True, out_ports=("ok",)))
    _mutate(page, _replace("#g-b", moved))
    _settle(page, before)
    kept = page.evaluate(
        "() => ['g-a', 'g-c'].map((id) => document.getElementById(id).__kept)"
    )
    assert kept == ["g-a", "g-c"]
    assert _position(page, "g-a") == ["20px", "40px"]
    assert _position(page, "g-c") == ["400px", "260px"]
    assert _path(page, "e1") != edge
    anchor = _call(page, "inAnchor", "b")
    assert _numbers(_path(page, "e1"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


def test_adding_a_node_and_its_edge_draws_the_edge(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    added = _html(session, _node("d", 700, 40, in_port=True))
    _mutate(
        page,
        _append("#g-nodes", added),
        _append("#g-edges", _span(_edge("e3", "b", "d", port="ok"))),
    )
    assert _settle(page, before) == before + 1
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    anchor = _call(page, "inAnchor", "d")
    assert _numbers(_path(page, "e3"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []


def test_removing_a_node_drops_its_edges(page, page_errors, session):
    edges = [*EDGES, _edge("e3", "b", "c", port="ok")]
    _serve(page, _stage(session, edges=edges))
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    before = _rendered(page)
    _mutate(page, _remove("#g-c"))
    _settle(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1"]
    assert page_errors == []


def test_adding_and_removing_an_edge_element_redraws_and_unfans_the_pair(
    page, page_errors, session
):
    _serve(page, _stage(session))
    plain = _path(page, "e1")
    before = _rendered(page)
    _mutate(page, _append("#g-edges", _span(_edge("e3", "a", "b", port="ok"))))
    before = _settle(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2", "e3"]
    # Two edges between a and b fan apart, so e1 bows away from its plain path.
    assert _path(page, "e1") != plain
    _mutate(
        page,
        "document.querySelector('#g-edges [data-edge-id=\"e3\"]').remove();",
    )
    _settle(page, before)
    assert [e["edge"] for e in _visible(page)] == ["e1", "e2"]
    assert _path(page, "e1") == plain
    assert page_errors == []


def test_removing_the_whole_nodes_layer_draws_nothing_and_fires_one_rendered(
    page, page_errors, session
):
    _serve(page, _stage(session))
    page.evaluate(
        "() => { window.__instance = pjx.graph.get(document.getElementById('g')); }"
    )
    before = _rendered(page)
    _mutate(page, _remove("#g-nodes"))
    assert _settle(page, before) == before + 1
    assert _visible(page) == []
    assert page.evaluate(
        "() => pjx.graph.get(document.getElementById('g')) === window.__instance"
    )
    assert page_errors == []


def test_a_node_removed_then_reinserted_keeps_its_stored_drop(
    page, page_errors, session
):
    seeded = json.dumps(
        {
            "view": IDENTITY_VIEW,
            "nodes": {"b": {"x": 300, "y": 150, "base": {"x": 400, "y": 40}}},
        }
    )
    _serve(page, _keyed(session), record=seeded)
    before = _rendered(page)
    _mutate(page, _remove("#g-b"))
    before = _settle(page, before)
    assert _raw(page) == seeded
    same = _html(session, _node("b", 400, 40, in_port=True, out_ports=("ok",)))
    _mutate(page, _append("#g-nodes", same))
    _settle(page, before)
    assert _position(page, "g-b") == ["300px", "150px"]
    assert _raw(page) == seeded
    assert page_errors == []


# Coalescing and the plane


def test_mutations_in_one_task_cause_one_reconcile(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(
        page,
        _replace("#g-a", _html(session, _trio()[0])),
        _replace("#g-b", _html(session, _trio(b=(400, 100))[1])),
        _append("#g-edges", _span(_edge("e3", "b", "c", port="ok"))),
    )
    assert _settle(page, before) == before + 1
    assert page_errors == []


def test_a_reconcile_does_not_trigger_another(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _mutate(page, _replace("#g-c", _html(session, _trio()[2])))
    after = _settle(page, before)
    assert after == before + 1
    _frames(page, 4)
    assert _rendered(page) == after
    assert page_errors == []


def test_calling_reconcile_by_hand_schedules_nothing(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    page.evaluate(RECONCILE, "g")
    _frames(page)
    assert _rendered(page) == before + 1
    assert page_errors == []


def test_selecting_a_node_fires_no_rendered(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    page.click(_title("g-b"))
    assert [e["type"] for e in _events(page, "select")] == ["select"]
    _frames(page)
    assert _rendered(page) == before
    assert page_errors == []


def test_dragging_a_wire_fires_no_rendered(page, page_errors, session):
    _serve(page, _stage(session))
    before = _rendered(page)
    _drag(page, _center(page, _port("g-a")), _center(page, _title("g-c")))
    assert [e["detail"] for e in _events(page, "wire")] == [
        {"from": "a", "port": "ok", "to": "c", "kind": "", "to_port": ""}
    ]
    _frames(page)
    assert _rendered(page) == before
    assert page_errors == []


def test_a_swap_inside_a_nested_stage_settles(page, page_errors, session):
    _serve(page, _nested(page, session), NESTED_CSS)
    inner, outer = _rendered(page, "in"), _rendered(page, "g")
    moved = _html(session, _node("y", 300, 60, "in", in_port=True))
    _mutate(page, _replace("#in-y", moved))
    _settle(page, inner, "in")
    counts = (_rendered(page, "in"), _rendered(page, "g"))
    assert counts[0] == inner + 1
    assert counts[1] <= outer + 1
    _frames(page, 4)
    assert (_rendered(page, "in"), _rendered(page, "g")) == counts
    anchor = _call(page, "inAnchor", "y", stage_id="in")
    assert _numbers(_path(page, "i1", "in"))[-2:] == pytest.approx(
        [anchor["x"], anchor["y"]], abs=0.01
    )
    assert page_errors == []
