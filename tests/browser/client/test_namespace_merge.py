"""pjx.js merges into window.pjx: re-running the bundle must not wipe builtins."""

from __future__ import annotations

from pyjinhx.client import read_pjx_runtime


def test_second_execution_keeps_state_installed_by_a_builtin(pjx_page):
    page = pjx_page("<div></div>")
    # Stand in for a builtin (popover, toast host) that self-guards on the
    # shared window.pjx namespace: pjx.js itself never defines this key, so it
    # can only survive a second run if the final assignment merges.
    page.evaluate("window.pjx.popover = { open: function () { return 'first'; } }")

    page.add_script_tag(content=read_pjx_runtime())

    assert page.evaluate("typeof window.pjx.popover") == "object"
    assert page.evaluate("window.pjx.popover.open()") == "first"


def test_second_execution_still_installs_the_core_api(pjx_page):
    page = pjx_page("<div></div>")
    page.add_script_tag(content=read_pjx_runtime())

    assert page.evaluate("typeof window.pjx.manifest") == "function"
    assert page.evaluate("typeof window.pjx.toast") == "function"
    assert page.evaluate("typeof window.pjx.loader.page") == "function"
