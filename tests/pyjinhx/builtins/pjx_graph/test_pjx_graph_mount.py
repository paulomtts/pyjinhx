"""pjx.graph.mount / pjx.graph.get and the engine's auto-boot, in real chromium.

Identity checks run inside page.evaluate, since JS objects do not round-trip
to Python. Stages are rendered by the real components; hand-written markup is
used only for deliberately broken stages.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pyjinhx.builtins.ui.pjx_graph import PJXGraph
from pyjinhx.builtins.ui.pjx_graph_nodes import PJXGraphNodes
from pyjinhx.rendering import render

if TYPE_CHECKING:
    from playwright.sync_api import Page

ASSET = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_graph"
    / "pjx_graph.js"
)

# Parses markup into a host that is never attached, so the observer cannot see it.
DETACHED = """html => {
    const host = document.createElement('div');
    host.innerHTML = html;
    return host.firstElementChild;
}"""

BROKEN = {
    ".pjx-graph__canvas": '<div id="bad" data-pjx-graph></div>',
    ".pjx-graph__viewport": (
        '<div id="bad" data-pjx-graph><div class="pjx-graph__canvas"></div></div>'
    ),
    "svg.pjx-graph__edge-plane": (
        '<div id="bad" data-pjx-graph><div class="pjx-graph__canvas">'
        '<div class="pjx-graph__viewport"><div class="pjx-graph__nodes"></div>'
        "</div></div></div>"
    ),
    ".pjx-graph__nodes": (
        '<div id="bad" data-pjx-graph><div class="pjx-graph__canvas">'
        '<div class="pjx-graph__viewport"><svg class="pjx-graph__edge-plane"></svg>'
        "</div></div></div>"
    ),
}


def _stage(session, stage_id: str = "g") -> str:
    nodes = PJXGraphNodes(id=f"{stage_id}-nodes")
    return render(PJXGraph(id=stage_id, nodes=nodes), session)


def _mount_error(page: Page, html: str) -> str:
    """The message mount throws for the detached stage parsed from html."""
    return page.evaluate(
        f"""html => {{
            const el = ({DETACHED})(html);
            try {{
                pjx.graph.mount(el);
            }} catch (error) {{
                return pjx.graph.get(el) === null ? error.message : 'registered';
            }}
            return 'did not throw';
        }}""",
        html,
    )


def test_namespace_carries_mount_and_get(graph_page, page_errors):
    assert graph_page.evaluate("typeof pjx.graph") == "object"
    assert graph_page.evaluate("typeof pjx.graph.mount") == "function"
    assert graph_page.evaluate("typeof pjx.graph.get") == "function"
    assert page_errors == []


def test_mount_is_idempotent_and_get_returns_the_instance(
    graph_page, page_errors, session
):
    graph_page.evaluate(
        "html => document.body.insertAdjacentHTML('beforeend', html)", _stage(session)
    )
    assert graph_page.evaluate(
        """() => {
            const el = document.getElementById('g');
            const first = pjx.graph.mount(el);
            const second = pjx.graph.mount(el);
            return first === second && pjx.graph.get(el) === first && first.root === el;
        }"""
    )
    assert page_errors == []


def test_mount_works_on_a_detached_stage(graph_page, page_errors, session):
    assert graph_page.evaluate(
        f"""html => {{
            const el = ({DETACHED})(html);
            const instance = pjx.graph.mount(el);
            document.body.appendChild(el);
            return pjx.graph.mount(el) === instance && pjx.graph.get(el) === instance;
        }}""",
        _stage(session),
    )
    assert page_errors == []


def test_mount_accepts_a_wrapped_node_layer(graph_page, page_errors, session):
    html = _stage(session).replace(
        '<div id="g-nodes" class="pjx-graph__nodes"></div>',
        '<section><div id="g-nodes" class="pjx-graph__nodes"></div></section>',
    )
    assert "<section>" in html
    assert graph_page.evaluate(
        f"html => pjx.graph.mount(({DETACHED})(html)) !== null", html
    )
    assert page_errors == []


@pytest.mark.parametrize("expression", ["null", "undefined", "'g'", "document"])
def test_mount_rejects_a_non_element(graph_page, page_errors, expression):
    message = graph_page.evaluate(
        f"""() => {{
            try {{
                pjx.graph.mount({expression});
            }} catch (error) {{
                return error.message;
            }}
            return 'did not throw';
        }}"""
    )
    assert message.startswith("pjx.graph.mount:")
    assert "[data-pjx-graph]" in message
    assert page_errors == []


def test_mount_rejects_an_element_without_the_marker(graph_page, page_errors):
    message = _mount_error(
        graph_page, "<div><div class='pjx-graph__canvas'></div></div>"
    )
    assert message.startswith("pjx.graph.mount:")
    assert "[data-pjx-graph]" in message
    assert page_errors == []


@pytest.mark.parametrize("selector", list(BROKEN))
def test_mount_names_the_first_missing_part(graph_page, page_errors, selector):
    message = _mount_error(graph_page, BROKEN[selector])
    assert message.startswith("pjx.graph.mount:")
    assert selector in message
    assert page_errors == []


def test_nested_graph_parts_do_not_satisfy_the_outer_stage(
    graph_page, page_errors, session
):
    # The inner graph sits where a panel goes: a direct child of the outer root.
    outer = f'<div id="outer" data-pjx-graph>{_stage(session, "inner")}</div>'
    message = _mount_error(graph_page, outer)
    assert message.startswith("pjx.graph.mount:")
    assert ".pjx-graph__canvas" in message
    assert page_errors == []


def test_failed_mount_registers_nothing_and_can_be_retried(graph_page, page_errors):
    assert graph_page.evaluate(
        f"""html => {{
            const el = ({DETACHED})(html);
            try {{ pjx.graph.mount(el); }} catch (error) {{}}
            if (pjx.graph.get(el) !== null) return 'registered';
            el.querySelector('.pjx-graph__viewport').insertAdjacentHTML(
                'beforeend', '<div class="pjx-graph__nodes"></div>');
            const instance = pjx.graph.mount(el);
            return pjx.graph.get(el) === instance;
        }}""",
        BROKEN[".pjx-graph__nodes"],
    )
    assert page_errors == []


def test_get_returns_null_without_throwing(graph_page, page_errors):
    assert graph_page.evaluate(
        """() => [
            pjx.graph.get(document.createElement('div')),
            pjx.graph.get(null),
            pjx.graph.get(undefined),
            pjx.graph.get('g'),
        ].every((value) => value === null)"""
    )
    assert page_errors == []


def test_reloading_keeps_mount_get_and_instances(graph_page, page_errors, session):
    graph_page.evaluate(
        f"""html => {{
            window.before = {{mount: pjx.graph.mount, get: pjx.graph.get}};
            window.el = ({DETACHED})(html);
            window.instance = pjx.graph.mount(window.el);
        }}""",
        _stage(session),
    )
    graph_page.add_script_tag(content=ASSET.read_text(encoding="utf-8"))
    assert graph_page.evaluate(
        """() => pjx.graph.mount === before.mount
            && pjx.graph.get === before.get
            && pjx.graph.get(el) === instance"""
    )
    assert page_errors == []
