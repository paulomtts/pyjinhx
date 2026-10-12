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


def _booted(stage_id: str = "g") -> str:
    return f"pjx.graph.get(document.getElementById('{stage_id}')) !== null"


def _append(page: Page, html: str) -> None:
    page.evaluate("html => document.body.insertAdjacentHTML('beforeend', html)", html)


def test_stage_present_before_the_asset_is_booted(page: Page, page_errors, session):
    page.set_content(f"<body>{_stage(session)}</body>")
    page.add_script_tag(content=ASSET.read_text(encoding="utf-8"))
    # Booted synchronously when the script runs after load.
    assert page.evaluate(_booted())
    assert page.evaluate(
        "() => pjx.graph.get(document.getElementById('g')).root"
        " === document.getElementById('g')"
    )
    assert page_errors == []


def test_asset_in_head_boots_the_stage_on_dom_content_loaded(
    page: Page, page_errors, console_errors, session
):
    asset = ASSET.read_text(encoding="utf-8")
    page.set_content(
        f"<html><head><script>{asset}</script></head>"
        f"<body>{_stage(session)}</body></html>"
    )
    assert page.evaluate(_booted())
    assert console_errors == []
    assert page_errors == []


def test_stage_streamed_by_the_parser_boots_without_errors(
    page: Page, page_errors, console_errors, session
):
    # The inline script pauses the parser after the stage element is created
    # but before its children exist; a live observer would mount it there.
    asset = ASSET.read_text(encoding="utf-8")
    stage = _stage(session).replace(
        '><div class="pjx-graph__canvas">',
        '><script>window.midStage = 1;</script><div class="pjx-graph__canvas">',
        1,
    )
    assert "midStage" in stage
    html = f"<html><head><script>{asset}</script></head><body>{stage}</body></html>"
    # A real navigation, not set_content: document.write would parse the whole
    # body before any observer callback could run.
    page.route(
        "http://pjx.test/",
        lambda route: route.fulfill(body=html, content_type="text/html"),
    )
    page.goto("http://pjx.test/")
    assert page.evaluate("window.midStage") == 1
    assert page.evaluate(_booted())
    assert console_errors == []
    assert page_errors == []


def test_stage_appended_after_load_is_booted(graph_page, page_errors, session):
    _append(graph_page, _stage(session))
    graph_page.wait_for_function(_booted())
    assert page_errors == []


def test_stage_nested_in_an_appended_wrapper_is_booted(
    graph_page, page_errors, session
):
    graph_page.evaluate(
        """html => {
            const wrapper = document.createElement('div');
            wrapper.innerHTML = '<section>' + html + '</section>';
            document.body.appendChild(wrapper);
        }""",
        _stage(session),
    )
    graph_page.wait_for_function(_booted())
    assert page_errors == []


def test_htmx_load_boots_a_stage_the_observer_did_not(graph_page, page_errors, session):
    # The marker is removed before the observer callback runs, so the
    # observer sees no stage; only htmx:load can mount it afterwards.
    result = graph_page.evaluate(
        """async html => {
            const turn = () => new Promise((resolve) => setTimeout(resolve));
            document.body.insertAdjacentHTML('beforeend', html);
            const el = document.getElementById('g');
            el.removeAttribute('data-pjx-graph');
            await turn();
            el.setAttribute('data-pjx-graph', '');
            await turn();
            const before = pjx.graph.get(el);
            el.dispatchEvent(new CustomEvent('htmx:load', {bubbles: true}));
            return [before === null, pjx.graph.get(el) !== null];
        }""",
        _stage(session),
    )
    assert result == [True, True]
    assert page_errors == []


def test_htmx_load_on_a_container_boots_its_stages(graph_page, page_errors, session):
    result = graph_page.evaluate(
        """async html => {
            const turn = () => new Promise((resolve) => setTimeout(resolve));
            document.body.insertAdjacentHTML('beforeend', '<div id="box"></div>');
            await turn();
            const box = document.getElementById('box');
            // The marker is off before the observer callback runs, so the
            // observer finds no stage among the added nodes.
            box.innerHTML = html;
            const el = document.getElementById('g');
            el.removeAttribute('data-pjx-graph');
            await turn();
            el.setAttribute('data-pjx-graph', '');
            box.dispatchEvent(new CustomEvent('htmx:load', {bubbles: true}));
            return pjx.graph.get(el) !== null;
        }""",
        _stage(session),
    )
    assert result is True
    assert page_errors == []


def test_broken_stage_is_logged_and_does_not_stop_its_neighbour(
    graph_page, page_errors, console_errors, session
):
    _append(graph_page, BROKEN[".pjx-graph__canvas"] + _stage(session))
    graph_page.wait_for_function(_booted())
    assert graph_page.evaluate(_booted("bad")) is False
    assert len(console_errors) == 1
    assert "pjx.graph.mount:" in console_errors[0]
    assert ".pjx-graph__canvas" in console_errors[0]
    assert page_errors == []


def test_reloading_installs_no_second_observer(
    graph_page, page_errors, console_errors, session
):
    graph_page.add_script_tag(content=ASSET.read_text(encoding="utf-8"))
    _append(graph_page, BROKEN[".pjx-graph__canvas"] + _stage(session))
    graph_page.wait_for_function(_booted())
    # One observer logs the broken stage once; a second one would log it twice.
    assert len(console_errors) == 1
    assert page_errors == []


def test_reinserted_stage_keeps_its_instance(graph_page, page_errors, session):
    _append(graph_page, _stage(session))
    graph_page.wait_for_function(_booted())
    assert graph_page.evaluate(
        """async () => {
            const el = document.getElementById('g');
            const instance = pjx.graph.get(el);
            el.remove();
            await new Promise((resolve) => setTimeout(resolve));
            document.body.appendChild(el);
            await new Promise((resolve) => setTimeout(resolve));
            return pjx.graph.get(el) === instance;
        }"""
    )
    assert page_errors == []


def test_replaced_stage_gets_a_new_instance(graph_page, page_errors, session):
    _append(graph_page, _stage(session))
    graph_page.wait_for_function(_booted())
    graph_page.evaluate(
        """html => {
            const old = document.getElementById('g');
            window.oldInstance = pjx.graph.get(old);
            old.outerHTML = html;
        }""",
        _stage(session),
    )
    graph_page.wait_for_function(_booted())
    assert graph_page.evaluate(
        """() => {
            const el = document.getElementById('g');
            const instance = pjx.graph.get(el);
            return instance !== oldInstance && instance.root === el
                && oldInstance.root !== el;
        }"""
    )
    assert page_errors == []


def test_sync_mount_before_the_observer_keeps_one_instance(
    graph_page, page_errors, console_errors, session
):
    assert graph_page.evaluate(
        """async html => {
            document.body.insertAdjacentHTML('beforeend', html);
            const el = document.getElementById('g');
            const instance = pjx.graph.mount(el);
            await new Promise((resolve) => setTimeout(resolve));
            return pjx.graph.get(el) === instance;
        }""",
        _stage(session),
    )
    assert console_errors == []
    assert page_errors == []
