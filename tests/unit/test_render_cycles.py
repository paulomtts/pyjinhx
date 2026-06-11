"""Render-cycle guard: cyclic cross-references render empty instead of recursing.

Repro for https://github.com/paulomtts/pyjinhx/issues/64 — a PascalCase tag
composing a registered component inside ``Registry.request_scope()`` used to
hit ``RecursionError`` because every registered instance is injected into the
render context and eagerly rendered.
"""

import logging

from jinja2 import Environment, FileSystemLoader

from pyjinhx import BaseComponent, Registry
from pyjinhx.renderer import Renderer
from tests.ui.unified_component import UnifiedComponent


def _renderer_for(tmp_path) -> Renderer:
    return Renderer(Environment(loader=FileSystemLoader(str(tmp_path))), auto_id=True)


def test_mutual_tag_reference_renders_each_component_once(tmp_path):
    class CycleLeft(BaseComponent):
        pass

    class CycleRight(BaseComponent):
        pass

    (tmp_path / "cycle_left.html").write_text(
        '<div class="cycle-left-marker"><CycleRight id="right-side"/></div>'
    )
    (tmp_path / "cycle_right.html").write_text(
        '<p class="cycle-right-marker"><CycleLeft id="left-side"/></p>'
    )

    renderer = _renderer_for(tmp_path)
    with Registry.request_scope():
        CycleLeft(id="left-side")
        CycleRight(id="right-side")
        rendered = renderer.render('<CycleLeft id="left-side"/>')

    assert rendered.count("cycle-left-marker") == 1
    assert rendered.count("cycle-right-marker") == 1


def test_panel_tag_composing_registered_component_renders(tmp_path):
    """The tutorial shape: a panel template tag-references a registered counter."""

    class TodoPanel(BaseComponent):
        pass

    class TodoTally(BaseComponent):
        remaining: int = 0

    (tmp_path / "todo_panel.html").write_text(
        '<section class="panel-marker"><TodoTally id="counter"/></section>'
    )
    (tmp_path / "todo_tally.html").write_text(
        '<span class="counter-marker">{{ remaining }} left</span>'
    )

    renderer = _renderer_for(tmp_path)
    with Registry.request_scope():
        TodoTally(id="counter", remaining=3)
        rendered = renderer.render('<TodoPanel id="panel"/>')

    assert rendered.count("panel-marker") == 1
    assert rendered.count("counter-marker") == 1
    assert "3 left" in rendered


def test_sequential_reuse_of_same_child_is_not_suppressed():
    child = UnifiedComponent(id="seq-child", text="Reused")
    parent = UnifiedComponent(id="seq-parent", nested=child, items=[child])

    rendered = str(parent.render())

    assert rendered.count('id="seq-child"') == 2
    assert rendered.count("Reused") >= 2


def test_self_reference_renders_empty_for_that_reference(tmp_path):
    class SelfLoop(BaseComponent):
        pass

    (tmp_path / "self_loop.html").write_text(
        '<div class="self-loop-marker">before<SelfLoop id="loop"/>after</div>'
    )

    renderer = _renderer_for(tmp_path)
    with Registry.request_scope():
        SelfLoop(id="loop")
        rendered = renderer.render('<SelfLoop id="loop"/>')

    assert rendered.count("self-loop-marker") == 1
    assert "beforeafter" in rendered


# ---------------------------------------------------------------------------
# Regression: same-id different-type nesting (issue 1a)
# Guard key granularity: two components with the same ``id`` but different
# types must both render fully — the old bare-``id`` key wrongly suppressed
# the inner component when outer was already on the stack.
# ---------------------------------------------------------------------------


def test_same_id_different_type_field_nesting_renders_both(tmp_path):
    """OuterShell(id='x', child=InnerChip(id='x')) — both render fully.

    Regression: the old bare-id guard keyed on self.id so OuterShell(id='x')
    would suppress InnerChip(id='x') even though they are different types.
    The outer's id appears in ``session.rendering`` but that must not block the
    inner component, which has a different type.

    The outer template uses a ``<RegInnerChip>`` tag so the renderer can
    find the inner template via ``_find_template_for_tag`` (which searches
    ``tmp_path``) rather than falling back to class-file discovery.
    """

    class RegInnerChip(BaseComponent):
        label: str = ""

    class RegOuterShell(BaseComponent):
        pass

    (tmp_path / "reg_inner_chip.html").write_text(
        '<span class="chip-marker">{{ label }}</span>'
    )
    # Outer references the registered chip via a PascalCase tag.
    (tmp_path / "reg_outer_shell.html").write_text(
        '<div class="shell-marker"><RegInnerChip id="x"/></div>'
    )

    renderer = _renderer_for(tmp_path)
    with Registry.request_scope():
        RegInnerChip(id="x", label="hello")
        RegOuterShell(id="x")
        rendered = renderer.render('<RegOuterShell id="x"/>')

    assert "shell-marker" in rendered
    assert "chip-marker" in rendered
    assert "hello" in rendered


def test_same_id_different_type_inside_request_scope_renders_both(tmp_path):
    """Same regression: outer and inner share an id but differ in type.

    The outer template cross-references the inner via a PascalCase tag so that
    both templates are discoverable from ``tmp_path``.
    """

    class RegPebble(BaseComponent):
        label: str = ""

    class RegBoulder(BaseComponent):
        pass

    (tmp_path / "reg_pebble.html").write_text(
        '<span class="pebble-marker">{{ label }}</span>'
    )
    (tmp_path / "reg_boulder.html").write_text(
        '<div class="boulder-marker"><RegPebble id="shared"/></div>'
    )

    renderer = _renderer_for(tmp_path)
    with Registry.request_scope():
        RegPebble(id="shared", label="world")
        RegBoulder(id="shared")
        rendered = renderer.render('<RegBoulder id="shared"/>')

    assert "boulder-marker" in rendered
    assert "pebble-marker" in rendered
    assert "world" in rendered


def test_cycle_suppression_logs_warning(tmp_path, caplog):
    """When a cycle is suppressed a warning is emitted."""

    class CycleWarn(BaseComponent):
        pass

    (tmp_path / "cycle_warn.html").write_text(
        '<div class="warn-marker"><CycleWarn id="w"/></div>'
    )

    renderer = _renderer_for(tmp_path)
    with Registry.request_scope():
        CycleWarn(id="w")
        with caplog.at_level(logging.WARNING, logger="pyjinhx"):
            renderer.render('<CycleWarn id="w"/>')

    assert any("render cycle suppressed" in r.message for r in caplog.records)
