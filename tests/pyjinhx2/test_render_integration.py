"""L0.4.8 integration tests — full render_level() -> stamp_root_attrs() ->
serialize() pipeline, exercised through the public API only (issue #287,
final subtask of #247).

Note: the plan for this issue described the pipeline as
`render() -> stamp_root_attrs() -> serialize()`, but `render()` already
returns a finished string (it calls `render_level()` then `serialize()`
internally) — passing its output to `stamp_root_attrs()` (which needs a
`RenderedLevel`) would fail immediately. These tests use `render_level()`
instead, which is the actual `RenderedLevel`-returning step in the pipeline
and the same function `test_render_level.py` exercises.

No production code changes are expected here (see docs/superpowers/plans/
2026-07-30-issue-287.md's Global Constraints for the one known, deliberate
wiring gap this file works around rather than fixes).
"""

from pathlib import Path

from pyjinhx2.component import BaseComponent, Slot
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.render import render_level
from pyjinhx2.root_attrs import stamp_root_attrs
from pyjinhx2.segments import serialize
from pyjinhx2.session import RenderSession


def test_childless_end_to_end_pipeline():
    """render -> stamp_root_attrs -> serialize on a childless component yields
    one string containing exactly one root element matching the template."""

    class CardComp(BaseComponent):
        title: str = "Hello"

    descriptor = ClassDescriptor(
        template_path=Path("integration_childless.html"),
        slot_fields=frozenset(),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": CardComp},
    )
    CardComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = CardComp()

    level = render_level(component, session)
    stamp_root_attrs(level, {})  # no-op stamp; still exercises the call
    output = serialize(level)

    assert output == '<article class="card">Hello</article>'
    assert output.count("<article") == 1
    assert output.count("</article>") == 1


def test_autoescape_scalar_survives_pipeline():
    """A scalar field containing <script>, &, and " comes out entity-escaped
    in the final serialized string, through the whole render pipeline."""

    class NoteComp(BaseComponent):
        body: str = """<script>alert("xss")</script> & co"""

    descriptor = ClassDescriptor(
        template_path=Path("integration_escape.html"),
        slot_fields=frozenset(),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": NoteComp},
    )
    NoteComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = NoteComp()

    level = render_level(component, session)
    stamp_root_attrs(level, {})
    output = serialize(level)

    assert "<script>" not in output
    assert "&lt;script&gt;" in output
    assert "&amp;" in output
    assert "&#34;" in output or "&quot;" in output
    assert output.startswith('<div class="note">')
    assert output.endswith("</div>")


def test_slot_field_raw_vs_scalar_escaped():
    """A Slot field marked `| safe` in its template comes out unescaped and
    byte-for-byte unchanged, contrasted in the same test against a plain
    scalar field carrying the same markup (escaped), proving the distinction
    is driven by the template's explicit `| safe`, not accidental."""

    class PanelComp(BaseComponent):
        label: str = "<b>hi</b>"
        markup: Slot = "<b>hi</b>"

    descriptor = ClassDescriptor(
        template_path=Path("integration_slot.html"),
        slot_fields=frozenset({"markup"}),
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": PanelComp},
    )
    PanelComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = PanelComp()

    level = render_level(component, session)
    stamp_root_attrs(level, {})
    output = serialize(level)

    assert '<span class="label">&lt;b&gt;hi&lt;/b&gt;</span>' in output
    assert '<span class="markup"><b>hi</b></span>' in output
