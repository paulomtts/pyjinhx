"""Edge drawing in real chromium: which edges a stage draws, their bezier
geometry and fan, the DOM they produce, their CSS and pjx:graph:rendered.

Every endpoint is a measured anchor, so stages are served from a real origin
with the graph CSS applied. Stages that check geometry start from a persisted
identity view, so nothing depends on the fit.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from markupsafe import Markup

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_edges import PJXGraphEdges
from pyjinhx.builtins.ui.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Page

UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "ui"
ASSET = UI / "pjx_graph" / "pjx_graph.js"
CSS = (UI / "pjx_graph" / "pjx_graph.css").read_text(encoding="utf-8") + (
    UI / "pjx_graph_node" / "pjx_graph_node.css"
).read_text(encoding="utf-8")
URL = "http://pjx.test/"
RECORD = "pjx-graph:flow"
IDENTITY = {"view": {"x": 0, "y": 0, "k": 1}}
# App semantic tokens the graph tokens default to; the test page has no theme.
THEME = ":root { --border: rgb(10, 20, 30); --text-muted: rgb(40, 50, 60); }"

# What a stage's own plane holds, in DOM order.
PLANE = """id => {
    const plane = document.querySelector('#' + id
        + ' > .pjx-graph__canvas > .pjx-graph__viewport > svg.pjx-graph__edge-plane');
    return Array.from(plane.children).map(el => ({
        tag: el.tagName, cls: el.getAttribute('class'), id: el.id,
        d: el.getAttribute('d'), edge: el.getAttribute('data-edge-id'),
        from: el.getAttribute('data-from'), to: el.getAttribute('data-to'),
        state: el.getAttribute('data-state')}));
}"""

CALL = """([id, method, args]) => {
    const instance = pjx.graph.get(document.getElementById(id));
    return instance[method](...args);
}"""

STYLE = """([id, selector]) => {
    const s = getComputedStyle(document.querySelector('#' + id + ' ' + selector));
    return {fill: s.fill, stroke: s.stroke, width: s.strokeWidth,
            events: s.pointerEvents, size: s.fontSize};
}"""

NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?")


def _node(node_id: str, x: float, y: float, stage_id: str = "g", **kw) -> PJXGraphNode:
    return PJXGraphNode(id=f"{stage_id}-{node_id}", node_id=node_id, x=x, y=y, **kw)


def _stage(session, nodes: list, stage_id: str = "g", edges=None, **graph) -> str:
    if edges is not None:
        graph["edges"] = PJXGraphEdges(id=f"{stage_id}-edges", edges=edges)
    layer = PJXGraphNodes(
        id=f"{stage_id}-nodes",
        nodes_html=PJXGraphNodes.join(render(node, session) for node in nodes),
    )
    return render(PJXGraph(id=stage_id, nodes=layer, **graph), session)


def _serve(page: Page, body: str, css: str = "") -> None:
    """Load body with the graph CSS (then css) and the asset; wait until every stage is ready."""
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}{css}</style></head>"
        f"<body>{body}<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)
    _wait_ready(page)


def _wait_ready(page: Page) -> None:
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('[data-pjx-graph]'))
            .every(s => !pjx.graph.get(s) || s.hasAttribute('data-pjx-graph-ready'))""",
        timeout=5000,
    )


def _seed(page: Page, record: dict, key: str = RECORD) -> None:
    """Store record under key before the page's own scripts run."""
    page.add_init_script(
        f"localStorage.setItem({json.dumps(key)}, {json.dumps(json.dumps(record))});"
    )


def _edge(edge_id: str, src: str, dst: str, **kw: str) -> dict[str, str]:
    return {"id": edge_id, "from": src, "to": dst, **kw}


def _trio(stage_id: str = "g") -> list[PJXGraphNode]:
    return [
        _node("a", 20, 40, stage_id, title="A", out_ports=("ok", "fail")),
        _node("b", 400, 40, stage_id, title="B", in_port=True),
        _node("c", 400, 260, stage_id, title="C", in_port=True),
    ]


def _plane(page: Page, stage_id: str = "g") -> list[dict]:
    return page.evaluate(PLANE, stage_id)


def _visible(page: Page, stage_id: str = "g") -> list[dict]:
    return [
        el
        for el in _plane(page, stage_id)
        if el["tag"] == "path" and (el["cls"] or "").split()[:1] == ["pjx-graph__edge"]
    ]


def _call(page: Page, method: str, *args, stage_id: str = "g"):
    return page.evaluate(CALL, [stage_id, method, list(args)])


def _numbers(d: str) -> list[float]:
    """The eight numbers of 'M x y C x y, x y, x y'."""
    return [float(n) for n in NUMBER.findall(d)]


def _expected(p1: dict, p2: dict, offset: float = 0.0) -> list[float]:
    dx = max(48, abs(p2["x"] - p1["x"]) * 0.5)
    length = math.hypot(p2["x"] - p1["x"], p2["y"] - p1["y"]) or 1
    nx = -(p2["y"] - p1["y"]) / length * offset
    ny = (p2["x"] - p1["x"]) / length * offset
    return [
        p1["x"],
        p1["y"],
        p1["x"] + dx + nx,
        p1["y"] + ny,
        p2["x"] - dx + nx,
        p2["y"] + ny,
        p2["x"],
        p2["y"],
    ]


# Which edges and in what DOM


def test_each_edge_draws_a_hit_path_then_its_visible_path(page, page_errors, session):
    _seed(page, IDENTITY)
    edges = [
        _edge("e1", "a", "b"),
        _edge("e2", "a", "c", port="fail"),
        _edge("e3", "b", "c"),
    ]
    _serve(page, _stage(session, _trio(), edges=edges, storage_key="flow"))
    plane = _plane(page)
    assert [(el["tag"], el["cls"], el["edge"]) for el in plane] == [
        ("path", "pjx-graph__edge-hit", "e1"),
        ("path", "pjx-graph__edge", "e1"),
        ("path", "pjx-graph__edge-hit", "e2"),
        ("path", "pjx-graph__edge", "e2"),
        ("path", "pjx-graph__edge-hit", "e3"),
        ("path", "pjx-graph__edge", "e3"),
    ]
    assert [
        (el["edge"], el["from"], el["to"], el["state"]) for el in _visible(page)
    ] == [
        ("e1", "a", "b", ""),
        ("e2", "a", "c", ""),
        ("e3", "b", "c", ""),
    ]
    for hit, line in zip(plane[0::2], plane[1::2], strict=True):
        assert hit["d"] == line["d"]
    assert page_errors == []


# Geometry


def test_paths_run_from_the_out_anchor_to_the_in_anchor(page, page_errors, session):
    _seed(page, IDENTITY)
    edges = [_edge("named", "a", "b", port="fail"), _edge("bare", "a", "c")]
    _serve(page, _stage(session, _trio(), edges=edges, storage_key="flow"))
    named, bare = _visible(page)
    fail = _call(page, "outAnchor", "a", "fail")
    default = _call(page, "outAnchor", "a")
    assert fail != pytest.approx(default, abs=0.5)
    for line, p1, p2 in [
        (named, fail, _call(page, "inAnchor", "b")),
        (bare, default, _call(page, "inAnchor", "c")),
    ]:
        numbers = _numbers(line["d"])
        assert numbers[:2] == pytest.approx([p1["x"], p1["y"]], abs=0.5)
        assert numbers[-2:] == pytest.approx([p2["x"], p2["y"]], abs=0.5)
    assert page_errors == []


def test_control_points_follow_the_bezier_formula(page, page_errors, session):
    _seed(page, IDENTITY)
    nodes = [
        _node("a", 20, 40, title="A"),
        _node("b", 700, 40, title="B"),
        _node("c", 300, 260, title="C"),
    ]
    edges = [_edge("long", "a", "b"), _edge("short", "a", "c")]
    _serve(page, _stage(session, nodes, edges=edges, storage_key="flow"))
    p1 = _call(page, "outAnchor", "a")
    long_line, short_line = _visible(page)
    for line, to in [(long_line, "b"), (short_line, "c")]:
        p2 = _call(page, "inAnchor", to)
        assert _numbers(line["d"]) == pytest.approx(_expected(p1, p2), abs=0.5)
    long_numbers = _numbers(long_line["d"])
    short_numbers = _numbers(short_line["d"])
    # Half the span when that is wider than 48, 48 when the span is short.
    assert long_numbers[2] - long_numbers[0] == pytest.approx(
        (long_numbers[6] - long_numbers[0]) / 2, abs=0.5
    )
    assert long_numbers[2] - long_numbers[0] > 48
    assert short_numbers[2] - short_numbers[0] == pytest.approx(48, abs=0.5)
    assert page_errors == []


def test_a_self_loop_uses_the_same_formula(page, page_errors, session):
    _seed(page, IDENTITY)
    nodes = [_node("a", 100, 80, title="A")]
    _serve(
        page,
        _stage(session, nodes, edges=[_edge("loop", "a", "a")], storage_key="flow"),
    )
    [line] = _visible(page)
    expected = _expected(_call(page, "outAnchor", "a"), _call(page, "inAnchor", "a"))
    assert _numbers(line["d"]) == pytest.approx(expected, abs=0.5)
    assert page_errors == []


# Skipped edges


def test_edges_to_unknown_or_hidden_nodes_are_skipped(
    page, page_errors, console_errors, session
):
    _seed(page, IDENTITY)
    hidden = render(_node("h", 400, 260, title="H"), session).replace(
        'style="', 'style="display:none;', 1
    )
    shown = "".join(
        render(node, session)
        for node in [_node("a", 20, 40, title="A"), _node("b", 400, 40, title="B")]
    )
    layer = PJXGraphNodes(id="g-nodes", nodes_html=Markup(shown + hidden))
    edges = render(
        PJXGraphEdges(
            id="g-edges",
            edges=[
                _edge("ghost", "a", "nope"),
                _edge("ok", "a", "b"),
                _edge("hidden", "h", "b"),
            ],
        ),
        session,
    )
    # Hand-written spans: one without data-to, one without port/state/label.
    raw = (
        '<span hidden data-pjx-graph-edge data-edge-id="raw" data-from="a"></span>'
        '<span hidden data-pjx-graph-edge data-edge-id="plain" data-from="b"'
        ' data-to="b"></span>'
    )
    _serve(
        page,
        render(
            PJXGraph(
                id="g", nodes=layer, edges=Markup(str(edges) + raw), storage_key="flow"
            ),
            session,
        ),
    )
    assert [(el["edge"], el["state"]) for el in _visible(page)] == [
        ("ok", ""),
        ("plain", ""),
    ]
    assert console_errors == []
    assert page_errors == []


# CSS


def test_edge_and_hit_path_styles_come_from_tokens(page, page_errors, session):
    _seed(page, IDENTITY)
    nodes = [_node("a", 20, 40, title="A"), _node("b", 400, 40, title="B")]
    other = [_node("a", 20, 40, "h", title="A"), _node("b", 400, 40, "h", title="B")]
    edges = [_edge("e1", "a", "b")]
    css = THEME + "#h { --pjx-graph-edge-stroke: rgb(1, 2, 3); }"
    _serve(
        page,
        _stage(session, nodes, edges=edges, storage_key="flow")
        + _stage(session, other, "h", edges=edges),
        css,
    )
    line = page.evaluate(STYLE, ["g", "path.pjx-graph__edge"])
    hit = page.evaluate(STYLE, ["g", "path.pjx-graph__edge-hit"])
    assert (line["fill"], line["stroke"], line["width"], line["events"]) == (
        "none",
        "rgb(10, 20, 30)",
        "1.5px",
        "none",
    )
    assert (hit["fill"], hit["stroke"], hit["width"], hit["events"]) == (
        "none",
        "rgba(0, 0, 0, 0)",
        "14px",
        "stroke",
    )
    assert (
        page.evaluate(STYLE, ["h", "path.pjx-graph__edge"])["stroke"] == "rgb(1, 2, 3)"
    )
    assert page_errors == []


# Fan

# b sits below and right of a, so the normal has both an x and a y part.
FAN_NODES = [("a", 20, 40), ("b", 400, 160), ("c", 400, 320)]


def _fan_nodes(stage_id: str = "g") -> list[PJXGraphNode]:
    return [_node(n, x, y, stage_id, title=n) for n, x, y in FAN_NODES]


def test_parallel_edges_fan_out_around_the_unfanned_path(page, page_errors, session):
    _seed(page, IDENTITY)
    three = [_edge("e1", "a", "b"), _edge("e2", "a", "b"), _edge("e3", "a", "b")]
    _serve(
        page,
        _stage(session, _fan_nodes(), edges=three, storage_key="flow")
        + _stage(session, _fan_nodes("h"), "h", edges=[_edge("e1", "a", "b")]),
    )
    p1 = _call(page, "outAnchor", "a")
    p2 = _call(page, "inAnchor", "b")
    lines = _visible(page)
    for line, offset in zip(lines, (-26, 0, 26), strict=True):
        assert _numbers(line["d"]) == pytest.approx(_expected(p1, p2, offset), abs=0.5)
    # The middle one is exactly a lone edge, endpoints included.
    [single] = _visible(page, "h")
    assert _numbers(lines[1]["d"]) == pytest.approx(_numbers(single["d"]), abs=0.5)
    for line in lines:
        assert _numbers(line["d"])[:2] == pytest.approx([p1["x"], p1["y"]], abs=0.5)
        assert _numbers(line["d"])[-2:] == pytest.approx([p2["x"], p2["y"]], abs=0.5)
    assert page_errors == []


def test_opposite_edges_share_one_fan_and_other_pairs_stay_unfanned(
    page, page_errors, session
):
    _seed(page, IDENTITY)
    edges = [_edge("ab", "a", "b"), _edge("ba", "b", "a"), _edge("ac", "a", "c")]
    _serve(page, _stage(session, _fan_nodes(), edges=edges, storage_key="flow"))
    ab, ba, ac = _visible(page)
    out_a = _call(page, "outAnchor", "a")
    assert _numbers(ab["d"]) == pytest.approx(
        _expected(out_a, _call(page, "inAnchor", "b"), -13), abs=0.5
    )
    assert _numbers(ba["d"]) == pytest.approx(
        _expected(_call(page, "outAnchor", "b"), _call(page, "inAnchor", "a"), 13),
        abs=0.5,
    )
    assert _numbers(ac["d"]) == pytest.approx(
        _expected(out_a, _call(page, "inAnchor", "c")), abs=0.5
    )
    assert page_errors == []


# State and label

LABELS = """id => Array.from(document.querySelectorAll('#' + id
        + ' > .pjx-graph__canvas > .pjx-graph__viewport > svg.pjx-graph__edge-plane > text'))
    .map(text => {
        const along = text.querySelector('textPath');
        const target = document.getElementById(along.getAttribute('href').slice(1));
        return {cls: text.getAttribute('class'), edge: text.getAttribute('data-edge-id'),
                text: along.textContent, offset: along.getAttribute('startOffset'),
                anchor: along.getAttribute('text-anchor'),
                elements: text.querySelectorAll('*').length,
                target: target && target.getAttribute('data-edge-id'),
                targetClass: target && target.getAttribute('class'),
                stage: target && target.closest('[data-pjx-graph]').id};
    })"""


def _labels(page: Page, stage_id: str = "g") -> list[dict]:
    return page.evaluate(LABELS, stage_id)


def test_the_state_becomes_a_class_modifier_when_it_is_one_token(
    page, page_errors, session
):
    _seed(page, IDENTITY)
    edges = [
        _edge("f", "a", "b", state="failed"),
        _edge("n", "a", "c"),
        _edge("s", "b", "c", state="very bad"),
    ]
    _serve(page, _stage(session, _trio(), edges=edges, storage_key="flow"))
    assert [(el["edge"], el["cls"], el["state"]) for el in _visible(page)] == [
        ("f", "pjx-graph__edge pjx-graph__edge--failed", "failed"),
        ("n", "pjx-graph__edge", ""),
        ("s", "pjx-graph__edge", "very bad"),
    ]
    assert page_errors == []


def _label(edge: str, text: str, stage: str = "g") -> dict:
    return {
        "cls": "pjx-graph__edge-label",
        "edge": edge,
        "text": text,
        "offset": "50%",
        "anchor": "middle",
        "elements": 1,
        "target": edge,
        "targetClass": "pjx-graph__edge",
        "stage": stage,
    }


def test_a_label_follows_its_path_as_literal_text(page, page_errors, session):
    _seed(page, IDENTITY)
    edges = [
        _edge("l", "a", "b", label="Retry"),
        _edge("m", "a", "c", label="<b>&"),
        _edge("x", "b", "c"),
    ]
    _serve(page, _stage(session, _trio(), edges=edges, storage_key="flow"))
    assert _labels(page) == [_label("l", "Retry"), _label("m", "<b>&")]
    assert page.evaluate("() => document.querySelectorAll('svg b').length") == 0
    assert [(el["tag"], el["edge"]) for el in _plane(page)] == [
        ("path", "l"),
        ("path", "l"),
        ("text", "l"),
        ("path", "m"),
        ("path", "m"),
        ("text", "m"),
        ("path", "x"),
        ("path", "x"),
    ]
    assert page_errors == []


def test_path_ids_are_unique_across_stages_reusing_edge_ids(page, page_errors, session):
    _seed(page, IDENTITY)
    edges = [_edge("zz1", "a", "b", label="one"), _edge("zz2", "a", "c", label="two")]
    _serve(
        page,
        _stage(session, _trio(), edges=edges, storage_key="flow")
        + _stage(session, _trio("h"), "h", edges=edges),
    )
    ids = page.evaluate(
        "() => Array.from(document.querySelectorAll('[id]'), el => el.id)"
    )
    assert len(ids) == len(set(ids))
    paths = [el["id"] for stage in ("g", "h") for el in _visible(page, stage)]
    assert len(paths) == 4
    assert all(path_id and "zz" not in path_id for path_id in paths)
    assert _labels(page) == [_label("zz1", "one"), _label("zz2", "two")]
    assert _labels(page, "h") == [_label("zz1", "one", "h"), _label("zz2", "two", "h")]
    assert page_errors == []


def test_markup_characters_in_ids_states_and_labels_stay_inert(
    page, page_errors, console_errors, session
):
    _seed(page, IDENTITY)
    odd = "<i>&'] x"
    edges = [_edge(odd, "a", "b", state="<i>&']", label=odd)]
    _serve(page, _stage(session, _trio(), edges=edges, storage_key="flow"))
    [line] = _visible(page)
    assert (line["edge"], line["state"], line["cls"]) == (
        odd,
        "<i>&']",
        "pjx-graph__edge pjx-graph__edge--<i>&']",
    )
    assert _labels(page) == [_label(odd, odd)]
    assert page.evaluate("() => document.querySelectorAll('i').length") == 0
    assert console_errors == []
    assert page_errors == []


def test_label_styles_come_from_tokens_and_an_app_state_rule_wins(
    page, page_errors, session
):
    _seed(page, IDENTITY)
    nodes = [_node("a", 20, 40, title="A"), _node("b", 400, 40, title="B")]
    edges = [_edge("e1", "a", "b", state="failed", label="Retry")]
    # App CSS loads after the builtin's; same specificity, so it wins.
    css = THEME + ".pjx-graph__edge--failed { stroke: rgb(200, 0, 0); }"
    _serve(page, _stage(session, nodes, edges=edges, storage_key="flow"), css)
    assert page.evaluate(STYLE, ["g", "path.pjx-graph__edge"])["stroke"] == (
        "rgb(200, 0, 0)"
    )
    label = page.evaluate(STYLE, ["g", "text.pjx-graph__edge-label"])
    assert (label["fill"], label["size"], label["events"]) == (
        "rgb(40, 50, 60)",
        "12px",
        "none",
    )
    assert page_errors == []
