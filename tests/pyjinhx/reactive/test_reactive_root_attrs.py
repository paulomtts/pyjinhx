"""L3.4 — the reactive on_rendered branch stamps data-pjx-id/data-pjx-hash.

The exhaustive suite (#465) for stamp_reactive_root_attrs and, transitively,
root_attrs.stamp_root_attrs/_override_tag as reached through a real
render_level() pass: tag shapes, override-vs-insert, quoting, composition with
an L0 pass-through stamp, and non-corruption of everything outside root_span.
Assertions are string-level throughout; the stamp is a splice, never a reparse.
"""

from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx._component import BaseComponent, Slot
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.reactive.component import ReactiveComponent
from pyjinhx.reactive.root_attrs import stamp_reactive_root_attrs
from pyjinhx.rendering import render_level
from pyjinhx.root_attrs import serialize_attr, stamp_root_attrs
from pyjinhx.segments import ChildRef, RenderedLevel, VerbatimParser, serialize
from pyjinhx.session import RenderSession

_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


class ReactiveWidget(ReactiveComponent):
    title: str = "hello"


class PlainWidget(BaseComponent):
    pass


def _descriptor_for(cls: type[BaseComponent], template: str) -> ClassDescriptor:
    return ClassDescriptor(
        template_path=_TEMPLATE_DIR / template,
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


ReactiveWidget.__pjx_descriptor__ = _descriptor_for(
    ReactiveWidget, "reactive_widget.html"
)
PlainWidget.__pjx_descriptor__ = _descriptor_for(PlainWidget, "plain_widget.html")


class VoidWidget(ReactiveComponent):
    pass


class PreStampedWidget(ReactiveComponent):
    pass


class AttrsWidget(ReactiveComponent):
    pass


class QuotingWidget(ReactiveComponent):
    title: str = 'a "quoted" title'


class ReactiveShell(ReactiveComponent):
    body: Slot = ""


VoidWidget.__pjx_descriptor__ = _descriptor_for(VoidWidget, "reactive_void.html")
PreStampedWidget.__pjx_descriptor__ = _descriptor_for(
    PreStampedWidget, "reactive_prestamped.html"
)
AttrsWidget.__pjx_descriptor__ = _descriptor_for(AttrsWidget, "reactive_attrs.html")
QuotingWidget.__pjx_descriptor__ = _descriptor_for(
    QuotingWidget, "reactive_widget.html"
)
ReactiveShell.__pjx_descriptor__ = ClassDescriptor(
    template_path=_TEMPLATE_DIR / "reactive_shell.html",
    slot_fields=frozenset({"body"}),
    children_field=None,
    css_paths=(),
    js_paths=(),
    strict=True,
    provenance={"template": ReactiveShell},
)


class InnerBadge(BaseComponent):
    pass


class MiddleWrap(BaseComponent):
    pass


class BuiltinRootWidget(ReactiveComponent):
    pass


class DoubleBuiltinRootWidget(ReactiveComponent):
    pass


InnerBadge.__pjx_descriptor__ = _descriptor_for(InnerBadge, "inner_badge.html")
MiddleWrap.__pjx_descriptor__ = _descriptor_for(MiddleWrap, "middle_wrap.html")
BuiltinRootWidget.__pjx_descriptor__ = _descriptor_for(
    BuiltinRootWidget, "reactive_builtin_root.html"
)
DoubleBuiltinRootWidget.__pjx_descriptor__ = _descriptor_for(
    DoubleBuiltinRootWidget, "reactive_double_root.html"
)


class PrologueRootWidget(ReactiveComponent):
    pass


PrologueRootWidget.__pjx_descriptor__ = _descriptor_for(
    PrologueRootWidget, "reactive_prologue_root.html"
)


@pytest.fixture
def registered_children():
    """Publish the nested-root fixture tags, then restore the prior mapping."""
    previous = discovery._registry.mapping
    discovery.register_class("inner_badge", InnerBadge)
    discovery.register_class("middle_wrap", MiddleWrap)
    yield
    discovery._registry.mapping = previous


@pytest.fixture
def session() -> RenderSession:
    """A session with only the reactive root-attr subscriber attached."""
    session = RenderSession()
    session.on_rendered.append(stamp_reactive_root_attrs)
    return session


def test_reactive_root_tag_carries_id_and_hash(session: RenderSession):
    component = ReactiveWidget(id="w1")

    html = serialize(render_level(component, session))

    assert 'data-pjx-id="w1"' in html
    assert f'data-pjx-hash="{component.state_hash()}"' in html


def test_stamped_hash_is_exactly_state_hash(session: RenderSession):
    """No recompute drift: the stamped digest is the one state_hash() returns."""
    component = ReactiveWidget(id="w2", title="different")

    html = serialize(render_level(component, session))

    stamped = html.split('data-pjx-hash="')[1].split('"')[0]
    assert stamped == component.state_hash()


def test_plain_component_root_tag_is_untouched(session: RenderSession):
    html = serialize(render_level(PlainWidget(id="p1"), session))

    assert "data-pjx-id" not in html
    assert "data-pjx-hash" not in html
    assert html == "<em>plain</em>"


def test_composes_with_a_pass_through_stamp_on_the_same_level(session: RenderSession):
    """L0 stamping still works alongside the reactive branch: the pass-through
    attr survives, and neither attribute is written twice."""
    component = ReactiveWidget(id="w3")

    level = render_level(component, session)
    stamp_root_attrs(level, {"class": "card"})
    html = serialize(level)

    assert 'class="card"' in html
    assert 'data-pjx-id="w3"' in html
    assert html.count("data-pjx-id=") == 1
    assert html.count("data-pjx-hash=") == 1


def test_re_stamping_the_same_level_overrides_rather_than_duplicates(
    session: RenderSession,
):
    """emit_rendered fires once per component, but the subscriber must still be
    idempotent against the override semantics stamp_root_attrs already has."""
    component = ReactiveWidget(id="w4")

    level = render_level(component, session)
    stamp_reactive_root_attrs(component, level, session)
    html = serialize(level)

    assert html.count("data-pjx-id=") == 1
    assert html.count("data-pjx-hash=") == 1


def test_self_closing_root_tag_gets_both_attrs_inserted(session: RenderSession):
    component = VoidWidget(id="v1")

    html = serialize(render_level(component, session))

    assert 'data-pjx-id="v1"' in html
    assert f'data-pjx-hash="{component.state_hash()}"' in html
    assert html.endswith("/>")
    assert " />" not in html  # no stray space introduced before the solidus


def test_self_closing_root_keeps_its_original_attributes(session: RenderSession):
    html = serialize(render_level(VoidWidget(id="v2"), session))

    assert 'src="x.png"' in html
    assert 'alt="a"' in html


def test_existing_data_pjx_attrs_are_overridden_not_duplicated(
    session: RenderSession,
):
    component = PreStampedWidget(id="p1")

    html = serialize(render_level(component, session))

    assert html.count("data-pjx-id=") == 1
    assert html.count("data-pjx-hash=") == 1
    assert 'data-pjx-id="p1"' in html
    assert 'data-pjx-id="stale"' not in html
    assert 'data-pjx-hash="deadbeef"' not in html
    assert f'data-pjx-hash="{component.state_hash()}"' in html


def test_override_happens_in_place_not_appended(session: RenderSession):
    """The stale attr's slot is reused, so the id stays left of the hash."""
    html = serialize(render_level(PreStampedWidget(id="p2"), session))

    assert html.index("data-pjx-id=") < html.index("data-pjx-hash=")


def test_fresh_insertion_when_the_root_has_no_data_pjx_attrs(session: RenderSession):
    html = serialize(render_level(ReactiveWidget(id="f1"), session))

    assert html.startswith("<span ")
    assert html.count("data-pjx-id=") == 1
    assert html.count("data-pjx-hash=") == 1


def test_unrelated_existing_attributes_are_preserved(session: RenderSession):
    html = serialize(render_level(AttrsWidget(id="a1"), session))

    assert 'id="outer"' in html
    assert 'class="a b"' in html
    assert 'data-keep="1"' in html
    assert "hidden" in html


def test_boolean_attribute_is_not_rewritten_into_a_valued_one(
    session: RenderSession,
):
    html = serialize(render_level(AttrsWidget(id="a2"), session))

    assert 'hidden=""' not in html
    assert 'hidden="hidden"' not in html


def test_a_hash_value_never_needs_quote_escaping(session: RenderSession):
    """A hex digest is quote-free by construction, so the stamp always uses '"'."""
    html = serialize(render_level(QuotingWidget(id="q1"), session))

    assert "data-pjx-hash='" not in html
    assert 'data-pjx-hash="' in html


def test_an_id_containing_a_double_quote_falls_back_to_single_quotes(
    session: RenderSession,
):
    component = QuotingWidget(id='we"ird')

    html = serialize(render_level(component, session))

    assert "data-pjx-id='we\"ird'" in html
    assert html.count("data-pjx-id=") == 1


def test_an_attr_value_with_both_quote_kinds_is_rejected():
    """serialize_attr has no escape hatch left, so it says so rather than
    emitting a tag that cannot be parsed back."""
    with pytest.raises(ValueError, match="data-pjx-id"):
        serialize_attr("data-pjx-id", "we\"ir'd")


def test_markup_outside_the_root_tag_is_byte_identical_after_stamping(
    session: RenderSession,
):
    """Everything the splice did not touch must survive unchanged."""
    plain = RenderSession()
    component = AttrsWidget(id="a3")

    level = render_level(component, plain)  # no subscriber attached
    before = serialize(level)
    before_start, before_end = level.root_span

    stamp_reactive_root_attrs(component, level, plain)
    after = serialize(level)
    after_start, after_end = level.root_span

    assert before[:before_start] == after[:after_start]
    assert before[before_end:] == after[after_end:]
    assert before[before_end:] == "<span>left</span>middle<b>right</b></div>"


def test_root_span_still_bounds_exactly_the_root_tag_after_stamping(
    session: RenderSession,
):
    component = AttrsWidget(id="a4")

    level = render_level(component, session)
    start, end = level.root_span
    root_segment = level.segments[0]

    assert isinstance(root_segment, str)
    tag = root_segment[start:end]
    assert tag.startswith("<div")
    assert tag.endswith(">")
    assert "data-pjx-id=" in tag
    assert "</div>" not in tag


def test_child_level_segments_are_untouched_by_the_parents_stamp(
    session: RenderSession,
):
    """A nested RenderedLevel is a sibling segment of the parent's root tag:
    the parent's splice edits segments[0] only and never reaches into it."""
    child = ReactiveWidget(id="inner")
    parent = ReactiveShell(id="outer", body=child)

    html = serialize(render_level(parent, session))

    assert "<p>before</p>" in html
    assert "<p>after</p>" in html
    assert 'data-pjx-id="outer"' in html
    assert 'data-pjx-id="inner"' in html
    assert html.count("data-pjx-id=") == 2
    assert html.index('data-pjx-id="outer"') < html.index("<p>before</p>")


def test_builtin_root_stamps_onto_the_nested_levels_root_tag(
    session: RenderSession, registered_children: None
):
    """#934: when the template root IS a child tag, render_level has already
    replaced segments[0] with that child's RenderedLevel — the stamp recurses
    into it instead of asserting on a str."""
    component = BuiltinRootWidget(id="b1")

    html = serialize(render_level(component, session))

    assert html == (
        f'<b class="badge" data-pjx-id="b1"'
        f' data-pjx-type="builtin_root_widget"'
        f' data-pjx-hash="{component.state_hash()}">badge</b>'
    )


def test_stamp_recurses_through_two_levels_of_nested_roots(
    session: RenderSession, registered_children: None
):
    """A builtin root whose own root is another child level: recursion, not a
    single hardcoded unwrap."""
    component = DoubleBuiltinRootWidget(id="b2")

    html = serialize(render_level(component, session))

    assert 'data-pjx-id="b2"' in html
    assert html.startswith('<b class="badge" data-pjx-id="b2"')
    assert html.count("data-pjx-id=") == 1


def test_empty_attrs_is_a_noop_when_the_root_segment_is_a_nested_level(
    registered_children: None,
):
    plain = RenderSession()
    level = render_level(BuiltinRootWidget(id="b3"), plain)
    before = serialize(level)

    assert stamp_root_attrs(level, {}) is level
    assert serialize(level) == before


def test_non_str_non_level_root_segment_raises_a_clear_error():
    level = RenderedLevel(
        segments=[ChildRef(tag="Unresolved", attrs={}, inner=None)],
        root_span=(0, 0),
        descriptor=None,
    )

    with pytest.raises(AssertionError, match="str or RenderedLevel"):
        stamp_root_attrs(level, {"class": "x"})


def test_stamping_the_parent_does_not_move_the_childs_attrs(
    session: RenderSession,
):
    child = ReactiveWidget(id="inner2")

    html = serialize(render_level(ReactiveShell(id="outer2", body=child), session))

    assert (
        f'<span data-pjx-id="inner2" data-pjx-type="reactive_widget"'
        f' data-pjx-hash="{child.state_hash()}">widget</span>' in html
    )


def test_whitespace_prologue_before_component_root(
    session: RenderSession, registered_children
):
    component = PrologueRootWidget(id="pro1")

    html = serialize(render_level(component, session))

    assert 'data-pjx-id="pro1"' in html
    assert html.lstrip().startswith("<b ")
    assert 'class="badge"' in html
    assert html.strip().endswith("</b>")


def test_whitespace_prologue_before_plain_div_root():
    source = '\n  <div class="card">body</div>\n'
    parser = VerbatimParser()
    parser.feed(source)
    parser.close()
    assert parser.root_span is not None
    level = RenderedLevel(
        segments=list(parser.segments),
        root_span=parser.root_span,
        descriptor=None,
    )

    html = serialize(stamp_root_attrs(level, {"data-x": "1", "class": "stamped"}))

    assert html == '\n  <div class="stamped" data-x="1">body</div>\n'


def test_multiple_whitespace_prologue_segments_before_root():
    level = RenderedLevel(
        segments=["\n", "   ", '<div id="d">x</div>'],
        root_span=(4, 16),
        descriptor=None,
    )

    html = serialize(stamp_root_attrs(level, {"data-y": "2"}))

    assert html == '\n   <div id="d" data-y="2">x</div>'
