"""Side panel open, close and back on a mounted stage, in real chromium.

The panel's state is DOM attributes and its buttons are real clicks on markup
the panel CSS shows and hides, so every stage is served from a real origin with
the graph and panel CSS applied. A document-level recorder installed before the
asset runs logs every panel and selection event, which also proves they bubble.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from markupsafe import Markup

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_node import PJXGraphNode
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.builtins.ui.pjx_graph_side_panel import PJXGraphSidePanel
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Page

UI = Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "ui"
ASSET = UI / "pjx_graph" / "pjx_graph.js"
CSS = "".join(
    (UI / name / f"{name}.css").read_text(encoding="utf-8")
    for name in ("pjx_graph", "pjx_graph_node", "pjx_graph_side_panel")
)
URL = "http://pjx.test/"
RECORD = "pjx-graph:flow"
IDENTITY = json.dumps({"view": {"x": 0, "y": 0, "k": 1}})

# Recorded at dispatch, from before the asset runs.
EVENTS = """window.__events = [];
['panel:before-close', 'panel:close', 'panel:open', 'before-select', 'select',
 'before-select-edge', 'select-edge', 'deselect'].forEach(
    (name) => document.addEventListener('pjx:graph:' + name, (event) => window.__events.push({
        type: name, detail: event.detail, target: event.target.id,
        cancelable: event.cancelable})));"""

# Calls an instance method; a throw comes back as its message.
CALL = """([stage, method, args]) => {
    try {
        const value = pjx.graph.get(document.getElementById(stage))[method](...args);
        return {value: value === undefined ? null : value};
    } catch (error) {
        return {error: error.message};
    }
}"""

# Calls a pjx.graph.panel function on the element with an id (null when no
# element has it); a throw comes back as its message.
PANEL = """([fn, stage, args]) => {
    try {
        const value = pjx.graph.panel[fn](document.getElementById(stage), ...args);
        return {value: value === undefined ? null : value};
    } catch (error) {
        return {error: error.message};
    }
}"""


def _node(node_id: str, x: float, y: float, stage_id: str = "g") -> PJXGraphNode:
    return PJXGraphNode(
        id=f"{stage_id}-{node_id}", node_id=node_id, x=x, y=y, title=node_id
    )


def _pair(stage_id: str = "g") -> list[PJXGraphNode]:
    return [_node("a", 10, 10, stage_id), _node("b", 330, 10, stage_id)]


def _panel(stage_id: str = "g", **kw) -> PJXGraphSidePanel:
    return PJXGraphSidePanel(id=f"{stage_id}-panel", title="Details", **kw)


def _stage(session, stage_id: str = "g", panel=None, **graph) -> str:
    """Stage stage_id with nodes a and b and, unless given another, a closed panel."""
    graph.setdefault("storage_key", "flow")
    nodes = (render(node, session) for node in _pair(stage_id))
    layer = PJXGraphNodes(id=f"{stage_id}-nodes", nodes_html=PJXGraphNodes.join(nodes))
    if panel is None:
        panel = _panel(stage_id)
    return render(PJXGraph(id=stage_id, nodes=layer, panel=panel, **graph), session)


def _serve(page: Page, body: str, css: str = "") -> None:
    """Seed an identity view, record panel and selection events, load body; wait."""
    page.add_init_script(
        f"localStorage.setItem({json.dumps(RECORD)}, {json.dumps(IDENTITY)});"
    )
    page.add_init_script(EVENTS)
    asset = ASSET.read_text(encoding="utf-8")
    html = (
        f"<html><head><style>{CSS}{css}</style></head>"
        f"<body>{body}<script>{asset}</script></body></html>"
    )
    page.route(URL, lambda route: route.fulfill(body=html, content_type="text/html"))
    page.goto(URL)
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('[data-pjx-graph]'))
            .every(s => !pjx.graph.get(s) || s.hasAttribute('data-pjx-graph-ready'))""",
        timeout=5000,
    )


def _events(page: Page) -> list[dict]:
    return page.evaluate("() => window.__events")


def _forget(page: Page) -> None:
    page.evaluate("() => { window.__events = []; }")


def _ev(kind: str, node_id: str | None, target: str = "g") -> dict:
    """One recorded panel event; its detail is always {id}."""
    return {
        "type": kind,
        "detail": {"id": node_id},
        "target": target,
        "cancelable": kind == "panel:before-close",
    }


def _veto(page: Page, kind: str) -> None:
    page.evaluate(
        "kind => document.addEventListener('pjx:graph:' + kind,"
        " (event) => event.preventDefault())",
        kind,
    )


def _call(page: Page, method: str, *args, stage_id: str = "g") -> dict:
    return page.evaluate(CALL, [stage_id, method, list(args)])


def _panel_call(page: Page, fn: str, *args, stage_id: str = "g") -> dict:
    return page.evaluate(PANEL, [fn, stage_id, list(args)])


def _state(page: Page, stage_id: str = "g") -> str | None:
    return page.get_attribute(f"#{stage_id}-panel", "data-open")


def _back(stage_id: str = "g") -> str:
    return f"#{stage_id}-panel > header > [data-pjx-graph-panel-back]"


def _close(stage_id: str = "g") -> str:
    return f"#{stage_id}-panel > header > [data-pjx-graph-panel-close]"


def _back_hidden(page: Page, stage_id: str = "g") -> bool:
    return page.evaluate(
        "selector => document.querySelector(selector).hidden", _back(stage_id)
    )


def _selected_nodes(page: Page) -> list[str]:
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('.pjx-graph__node--selected'))
            .map((node) => node.id)"""
    )


# open()


def test_open_shows_the_panel_and_fires_open_once(page, page_errors, session):
    _serve(page, _stage(session))
    assert _state(page) == "false"
    assert _panel_call(page, "open", "a") == {"value": True}
    assert _state(page) == "true"
    assert _events(page) == [_ev("panel:open", "a")]
    assert _back_hidden(page) is True
    assert page_errors == []


def test_opening_the_shown_id_again_fires_nothing_and_pushes_nothing(
    page, page_errors, session
):
    _serve(page, _stage(session))
    _panel_call(page, "open", "a")
    _forget(page)
    assert _panel_call(page, "open", "a") == {"value": True}
    assert _events(page) == []
    assert _back_hidden(page) is True
    assert page_errors == []


def test_opening_a_second_id_shows_the_back_button(page, page_errors, session):
    _serve(page, _stage(session))
    _panel_call(page, "open", "a")
    _forget(page)
    assert _panel_call(page, "open", "b") == {"value": True}
    assert _events(page) == [_ev("panel:open", "b")]
    assert _back_hidden(page) is False
    assert _state(page) == "true"
    assert page_errors == []


def test_an_open_listener_sees_the_panel_already_open_and_synced(
    page, page_errors, session
):
    _serve(page, _stage(session))
    page.evaluate(
        """() => {
            window.__seen = [];
            document.addEventListener('pjx:graph:panel:open', () => {
                const panel = document.getElementById('g-panel');
                window.__seen.push([panel.getAttribute('data-open'),
                    panel.querySelector('[data-pjx-graph-panel-back]').hidden]);
            });
        }"""
    )
    _panel_call(page, "open", "a")
    _panel_call(page, "open", "b")
    assert page.evaluate("() => window.__seen") == [["true", True], ["true", False]]
    assert page_errors == []


def test_open_never_touches_the_panel_content(page, page_errors, session):
    _serve(page, _stage(session, panel=_panel(content=Markup("<p>Body</p>"))))
    _panel_call(page, "open", "a")
    content = page.inner_html("#g-panel [data-pjx-graph-panel-content]")
    assert content == "<p>Body</p>"
    assert page_errors == []


# back()


def test_the_back_button_returns_to_the_previous_id(page, page_errors, session):
    _serve(page, _stage(session))
    _panel_call(page, "open", "a")
    _panel_call(page, "open", "b")
    assert _back_hidden(page) is False
    _forget(page)
    page.click(_back())
    assert _events(page) == [_ev("panel:open", "a")]
    assert _back_hidden(page) is True
    assert _state(page) == "true"
    _forget(page)
    assert _panel_call(page, "back") == {"value": False}
    assert _events(page) == []
    assert page_errors == []


def test_back_walks_through_three_entries(page, page_errors, session):
    _serve(page, _stage(session))
    for node_id in ("a", "b", "c"):
        _panel_call(page, "open", node_id)
    _forget(page)
    assert _panel_call(page, "back") == {"value": True}
    assert _events(page) == [_ev("panel:open", "b")]
    assert _back_hidden(page) is False
    _forget(page)
    assert _panel_call(page, "back") == {"value": True}
    assert _events(page) == [_ev("panel:open", "a")]
    assert _back_hidden(page) is True
    assert _state(page) == "true"
    assert page_errors == []


def test_back_with_an_empty_history_returns_false(page, page_errors, session):
    _serve(page, _stage(session))
    assert _panel_call(page, "back") == {"value": False}
    assert _state(page) == "false"
    assert _events(page) == []
    assert page_errors == []


# close()


def test_the_close_button_closes_and_resets_the_history(page, page_errors, session):
    _serve(page, _stage(session))
    _panel_call(page, "open", "a")
    _panel_call(page, "open", "b")
    _forget(page)
    page.click(_close())
    assert _events(page) == [_ev("panel:before-close", "b"), _ev("panel:close", "b")]
    assert _state(page) == "false"
    assert _back_hidden(page) is True
    _forget(page)
    _panel_call(page, "open", "a")
    assert _events(page) == [_ev("panel:open", "a")]
    assert _back_hidden(page) is True
    assert page_errors == []


def test_close_returns_true_and_closing_twice_fires_nothing(page, page_errors, session):
    _serve(page, _stage(session))
    _panel_call(page, "open", "a")
    _forget(page)
    assert _panel_call(page, "close") == {"value": True}
    assert _events(page) == [_ev("panel:before-close", "a"), _ev("panel:close", "a")]
    assert _state(page) == "false"
    _forget(page)
    assert _panel_call(page, "close") == {"value": True}
    assert _events(page) == []
    assert page_errors == []


def test_a_prevented_before_close_keeps_the_panel_and_its_history(
    page, page_errors, session
):
    _serve(page, _stage(session))
    _panel_call(page, "open", "a")
    _panel_call(page, "open", "b")
    _veto(page, "panel:before-close")
    _forget(page)
    page.click(_close())
    assert _panel_call(page, "close") == {"value": False}
    assert _events(page) == [
        _ev("panel:before-close", "b"),
        _ev("panel:before-close", "b"),
    ]
    assert _state(page) == "true"
    assert _back_hidden(page) is False
    _forget(page)
    assert _panel_call(page, "back") == {"value": True}
    assert _events(page) == [_ev("panel:open", "a")]
    assert page_errors == []


def test_a_server_open_panel_closes_with_a_null_id(page, page_errors, session):
    _serve(page, _stage(session, panel=_panel(open=True)))
    assert _panel_call(page, "back") == {"value": False}
    page.click(_close())
    assert _events(page) == [
        _ev("panel:before-close", None),
        _ev("panel:close", None),
    ]
    assert _state(page) == "false"
    assert page_errors == []


def test_close_listeners_see_the_panel_before_and_after(page, page_errors, session):
    _serve(page, _stage(session))
    _panel_call(page, "open", "a")
    _panel_call(page, "open", "b")
    page.evaluate(
        """() => {
            window.__seen = [];
            ['panel:before-close', 'panel:close'].forEach((name) =>
                document.addEventListener('pjx:graph:' + name, () => {
                    const panel = document.getElementById('g-panel');
                    window.__seen.push([name, panel.getAttribute('data-open'),
                        panel.querySelector('[data-pjx-graph-panel-back]').hidden]);
                }));
        }"""
    )
    page.click(_close())
    assert page.evaluate("() => window.__seen") == [
        ["panel:before-close", "true", False],
        ["panel:close", "false", True],
    ]
    assert page_errors == []


# An app may write its own panel; only the data attributes matter.
APP_PANEL = Markup(
    '<aside id="g-panel" data-pjx-graph-panel data-open="false">'
    '<button type="button" data-pjx-graph-panel-close><span id="g-x">x</span></button>'
    "</aside>"
)


def test_an_app_made_panel_without_a_back_button_still_works(
    page, page_errors, session
):
    _serve(page, _stage(session, panel=APP_PANEL))
    assert _panel_call(page, "open", "a") == {"value": True}
    assert _panel_call(page, "open", "b") == {"value": True}
    assert _panel_call(page, "back") == {"value": True}
    _forget(page)
    page.click("#g-x")
    assert _events(page) == [_ev("panel:before-close", "a"), _ev("panel:close", "a")]
    assert _state(page) == "false"
    assert page_errors == []


# Errors


@pytest.mark.parametrize("fn", ["open", "close", "back"])
@pytest.mark.parametrize("target", ["plain", "missing"], ids=["div", "null"])
def test_a_panel_function_rejects_what_is_not_a_mounted_stage(
    page, page_errors, session, fn, target
):
    _serve(page, _stage(session) + '<div id="plain"></div>')
    assert _panel_call(page, fn, "a", stage_id=target) == {
        "error": f"pjx.graph.panel.{fn}: expected a mounted [data-pjx-graph] stage"
    }
    assert _events(page) == []
    assert page_errors == []


@pytest.mark.parametrize("fn", ["open", "close", "back"])
def test_a_panel_function_rejects_a_stage_without_a_panel(
    page, page_errors, session, fn
):
    _serve(page, _stage(session, panel=""))
    assert _panel_call(page, fn, "a") == {
        "error": f"pjx.graph.panel.{fn}: stage has no [data-pjx-graph-panel]"
    }
    assert _events(page) == []
    assert page_errors == []


@pytest.mark.parametrize("bad", ["", 1, None], ids=["empty", "number", "null"])
def test_open_rejects_an_id_that_is_not_a_non_empty_string(
    page, page_errors, session, bad
):
    _serve(page, _stage(session))
    assert _panel_call(page, "open", bad) == {
        "error": "pjx.graph.panel.open: expected a non-empty string id"
    }
    assert _state(page) == "false"
    assert _events(page) == []
    assert page_errors == []
