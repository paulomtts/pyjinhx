"""The always-on runtime CSS: one server-emitted <style id="pjx-style"> per render."""

from __future__ import annotations

from pyjinhx.assets import emit_assets
from pyjinhx.client.inject import inject_runtime
from pyjinhx.session import RenderSession


def emitted() -> str:
    session = RenderSession()
    inject_runtime(session)
    return emit_assets(session)


def test_the_style_block_is_emitted_once():
    assert emitted().count('<style id="pjx-style">') == 1


def test_the_style_block_defines_the_skeleton_and_spinner_classes():
    css = emitted()
    assert ".pjx-loading--skeleton" in css
    assert ".pjx-loading--spinner" in css


def test_the_style_rules_read_overridable_custom_properties():
    css = emitted()
    assert "--pjx-skeleton-color" in css
    assert "--pjx-spinner-size" in css


def test_a_second_inject_on_the_same_session_does_not_duplicate_it():
    session = RenderSession()
    inject_runtime(session)
    inject_runtime(session)
    assert emit_assets(session).count('<style id="pjx-style">') == 1
