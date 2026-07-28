import os
import tempfile
from typing import Annotated

from jinja2 import Environment, FileSystemLoader
from pydantic import Field

from pyjinhx import AssetMode, BaseComponent
from pyjinhx.base import PjxSlot
from pyjinhx.renderer import Renderer


def test_component_template_can_expand_custom_tags():
    """Test that PascalCase tags inside component templates are expanded."""

    class Child(BaseComponent):
        text: str

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "child.html"), "w") as file:
            file.write('<span id="{{ id }}">{{ text }}</span>\n')

        with open(os.path.join(temp_dir, "parent.html"), "w") as file:
            file.write(
                '<div id="{{ id }}"><Child id="child-1" text="{{ child_text }}"/></div>\n'
            )

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render('<Parent id="parent-1" child_text="Hello"/>')

        assert rendered == '<div id="parent-1" child_text="Hello"><span id="child-1">Hello</span></div>'


def test_nested_custom_tags_in_renderer():
    """Test deeply nested PascalCase tags are all expanded."""

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "outer.html"), "w") as file:
            file.write('<section id="{{ id }}">{{ content }}</section>\n')

        with open(os.path.join(temp_dir, "inner.html"), "w") as file:
            file.write('<p id="{{ id }}">{{ text }}</p>\n')

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render(
            '<Outer id="outer-1"><Inner id="inner-1" text="Nested content"/></Outer>'
        )

        assert (
            rendered
            == '<section id="outer-1"><p id="inner-1" text="Nested content">Nested content</p></section>'
        )


def test_sibling_tag_alongside_already_expanded_children_still_expands():
    """A row-like component whose slot content is already-fully-expanded
    child HTML, but whose OWN template has one further literal sibling
    custom tag, must still expand that sibling correctly (this is the
    opacify/restore path exercised end-to-end)."""

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "badge.html"), "w") as file:
            file.write('<span id="{{ id }}" class="badge">{{ text }}</span>\n')

        with open(os.path.join(temp_dir, "icon.html"), "w") as file:
            file.write('<i id="{{ id }}" class="icon-{{ name }}"></i>\n')

        with open(os.path.join(temp_dir, "table_row.html"), "w") as file:
            # {{ content }} carries already-expanded Badge/Icon children;
            # the trailing <Icon .../> is a NEW sibling tag the row's own
            # template introduces, needing expansion at THIS level.
            # Note: named "TableRow" (not "Row") to avoid colliding with the
            # module-level `class Row(ReactiveComponent...)` registered
            # globally by tests/unit/test_instance_key_cache.py.
            file.write(
                '<tr id="{{ id }}">{{ content }}<Icon id="trail-1" name="chevron"/></tr>\n'
            )

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render(
            '<TableRow id="row-1">'
            '<Badge id="b1" text="New"/><Icon id="i1" name="star"/>'
            "</TableRow>"
        )

        # Note: "text"/"name" leak onto the leaf root tags as pass-through
        # extra attrs — this is pre-existing, unrelated-to-Task-2 behavior
        # (see test_nested_custom_tags_in_renderer above, where Inner's
        # "text" attr leaks onto <p> the same way).
        assert rendered == (
            '<tr id="row-1">'
            '<span id="b1" class="badge" text="New">New</span>'
            '<i id="i1" class="icon-star" name="star"></i>'
            '<i id="trail-1" class="icon-chevron" name="chevron"></i>'
            "</tr>"
        )


def test_literal_custom_tag_in_python_supplied_content_still_expands():
    """Regression guard: a component constructed directly in Python with a
    literal PascalCase tag string in its content/slot field must still be
    expanded by the parent's own expand_custom_tags call (case B — verified
    manually during design; must not be broken by opacifying slot values).

    Uses the classless ``component()`` factory (rather than hand-written
    ``BaseComponent`` subclasses) so template lookup resolves against the
    temp dir regardless of where this test module itself lives; asset
    injection is suppressed so the root-level ``.render()`` call is directly
    comparable by equality.
    """
    from pyjinhx import AssetMode, component

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "icon.html"), "w") as file:
            file.write('<i id="{{ id }}" class="icon-{{ name }}"></i>\n')

        with open(os.path.join(temp_dir, "card.html"), "w") as file:
            file.write('<article id="{{ id }}">{{ content }}</article>\n')

        env = Environment(loader=FileSystemLoader(temp_dir))
        Renderer.set_default_environment(env)
        Renderer.set_default_js_mode(AssetMode.NONE)
        Renderer.set_default_css_mode(AssetMode.NONE)
        try:
            Card = component("Card")
            rendered = str(
                Card(id="c1", content='<Icon id="i1" name="star"/>').render()
            )
        finally:
            Renderer.set_default_environment(None)
            Renderer.set_default_js_mode(AssetMode.INLINE)
            Renderer.set_default_css_mode(AssetMode.INLINE)

        # Note: "name" leaks onto <i> as a pass-through extra attr — same
        # pre-existing, Task-2-unrelated behavior noted in the sibling test
        # above.
        assert rendered == (
            '<article id="c1"><i id="i1" class="icon-star" name="star"></i></article>'
        )


def test_empty_slot_stays_falsy_after_opacify_regression_guard():
    """Regression guard for the empty-value guard inside
    `_collect_opacifiable_slot_values`: an empty slot value is never
    collected as an opacify candidate, so a template's `{% if slot %}`
    truthiness check isn't flipped from falsy to truthy by a non-empty
    placeholder token appearing where the real (empty) value should be. A
    prior implementer discovered this only via golden-file tests
    (lazy_load, accordion, tabs, ...) not covered by this diff; this test
    would fail if that guard were removed.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "card.html"), "w") as file:
            file.write(
                '<div id="{{ id }}">{% if content %}HAS{% else %}NONE{% endif %}</div>\n'
            )

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        # Bare tag, no children -> content is an empty string/Markup.
        rendered = renderer.render('<Card id="card-1"/>')

        assert "NONE" in rendered
        assert "HAS" not in rendered


def test_opacified_slot_length_check_sees_real_content_not_placeholder():
    """Proves the old design's "emit-only" limitation is gone for a
    component's own direct inspection of its own slot value: a template
    that *inspects* an already-opacifiable slot value (here, via `|length`)
    now sees the REAL already-expanded HTML, not a short placeholder token.

    Output-substitution opacifies only against the *rendered* markup, after
    `template.render()` has already run against the real, unmodified
    context -- so `{{ content|length }}` observes the true length of the
    real embedded HTML, exactly as it would without this perf optimization
    at all. (This guarantee is specifically about a component inspecting its
    OWN slot value in its OWN template; see
    test_nested_opacified_slot_seen_as_placeholder_by_own_template below for
    the narrower, still-open case of a value passed further into a nested
    custom tag's own template.)
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Distinct tag names ("LengthChild"/"LengthWrapper") avoid colliding
        # with the "Child" Python class registered by another test in this
        # module (BaseComponent subclasses resolve globally by name), which
        # would otherwise make this test's outcome depend on test order.
        with open(os.path.join(temp_dir, "length_child.html"), "w") as file:
            file.write('<span id="{{ id }}">{{ text }}</span>\n')

        with open(os.path.join(temp_dir, "length_wrapper.html"), "w") as file:
            file.write('<div id="{{ id }}">{{ content|length }}</div>\n')

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render(
            '<LengthWrapper id="w1">'
            '<LengthChild id="c1" text="Hello there"/>'
            "</LengthWrapper>"
        )

        real_child_html = '<span id="c1" text="Hello there">Hello there</span>'
        # The real, already-expanded child HTML is far longer than a
        # single-digit placeholder token length would be.
        assert len(real_child_html) > 9
        assert rendered == f'<div id="w1">{len(real_child_html)}</div>'


def test_opacified_slot_can_both_emit_and_inspect_the_same_value():
    """The core improvement over the old design: a template that both
    *emits* an already-opacifiable slot value (`{{ content }}`) AND
    *inspects* that exact same value (`{{ content|length }}`) in the same
    template now gets consistent, real results for both -- proving
    output-substitution isn't just "inspecting no longer sees a stale
    placeholder" in isolation, but that emit and inspect agree with each
    other, exactly as they would without this perf optimization at all.

    Under the old (context-substitution) design this would have emitted the
    real HTML (since the placeholder gets restored in the final output) but
    reported the placeholder token's short length -- an internally
    inconsistent result a template author would find surprising.

    Note: this consistency guarantee is specifically about a component
    emitting and inspecting its OWN slot value within its OWN template. It
    does not extend to a value passed further into a nested custom tag's own
    template -- see
    test_nested_opacified_slot_seen_as_placeholder_by_own_template below.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "emit_inspect_child.html"), "w") as file:
            file.write('<span id="{{ id }}">{{ text }}</span>\n')

        with open(os.path.join(temp_dir, "emit_inspect_wrapper.html"), "w") as file:
            file.write(
                '<div id="{{ id }}">{{ content }}|{{ content|length }}</div>\n'
            )

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render(
            '<EmitInspectWrapper id="w1">'
            '<EmitInspectChild id="c1" text="Hello there"/>'
            "</EmitInspectWrapper>"
        )

        real_child_html = '<span id="c1" text="Hello there">Hello there</span>'
        assert rendered == (
            f'<div id="w1">{real_child_html}|{len(real_child_html)}</div>'
        )


def test_list_slot_values_recurse_through_opacify_and_restore_correctly():
    """`_collect_opacifiable_slot_values` recurses into list-shaped slot
    values (the same shape `base._wrap_slot_value` produces for a field like
    `PJXDropdown.items: list[str | BaseComponent]`). Exercise a slot field
    that's a `list[str]` with a mix of:
    - an already-fully-expanded value containing no tag-looking substring
      (collected as a candidate, opacified in the rendered output, then
      restored via its placeholder token), and
    - a literal value containing a real custom tag (never collected as a
      candidate, so it still gets expanded via the full `expand_custom_tags`
      scan, exactly as before this perf change).
    """

    class Badge(BaseComponent):
        text: str = ""

    class Menu(BaseComponent):
        items: Annotated[list[str], PjxSlot()] = Field(default_factory=list)

    # Template resolution walks up from the *class's own module file* (here,
    # this test module) to find its co-located template, so the fixture
    # templates must live next to this test file rather than in an unrelated
    # tempdir -- written here and removed in `finally`.
    test_dir = os.path.dirname(__file__)
    badge_path = os.path.join(test_dir, "badge.html")
    menu_path = os.path.join(test_dir, "menu.html")
    with open(badge_path, "w") as file:
        file.write('<span id="{{ id }}" class="badge">{{ text }}</span>\n')
    with open(menu_path, "w") as file:
        file.write(
            '<ul id="{{ id }}">{% for item in items %}<li>{{ item }}</li>'
            "{% endfor %}</ul>\n"
        )

    env = Environment(loader=FileSystemLoader(test_dir))
    Renderer.set_default_environment(env)
    Renderer.set_default_js_mode(AssetMode.NONE)
    Renderer.set_default_css_mode(AssetMode.NONE)
    try:
        rendered = str(
            Menu(
                id="m1",
                items=[
                    "<em>already expanded</em>",
                    '<Badge id="b1" text="New"/>',
                ],
            ).render()
        )
    finally:
        Renderer.set_default_environment(None)
        Renderer.set_default_js_mode(AssetMode.INLINE)
        Renderer.set_default_css_mode(AssetMode.INLINE)
        os.remove(badge_path)
        os.remove(menu_path)

    assert rendered == (
        '<ul id="m1">'
        "<li><em>already expanded</em></li>"
        '<li><span id="b1" class="badge">New</span></li>'
        "</ul>"
    )


def test_marker_already_present_in_rendered_output_does_not_corrupt_render():
    """Regression guard for the placeholder-marker-collision finding: if the
    rendered markup already contains the ``_SLOT_PLACEHOLDER_CHAR`` marker
    BEFORE opacification -- e.g. because a template embeds an attribute
    value that happens to contain the same char sequence a real token would
    take -- `_opacify_rendered_markup` must not opacify anything at that
    level. Opacifying on top of pre-existing marker text would let the
    restore pass splice an unrelated slot's HTML into the wrong location
    (reproduced by the reviewer as both a crash and, more generally, an HTML
    /attribute injection).

    This exercises the guard end-to-end: a real already-expanded slot value
    (`content`) sits alongside an attribute (`evil`) whose value is shaped
    exactly like a placeholder token. The render must succeed and must
    produce the same structure as an equivalent render where `evil` is an
    ordinary, marker-free string -- i.e. the marker's mere presence must not
    corrupt anything, crash anything, or skip real tag expansion (`Icon`
    below still must expand normally).
    """
    from pyjinhx.renderer import _SLOT_PLACEHOLDER_CHAR

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "leaf.html"), "w") as file:
            file.write('<span id="{{ id }}">{{ text }}</span>\n')

        with open(os.path.join(temp_dir, "icon.html"), "w") as file:
            file.write('<i id="{{ id }}" class="icon-{{ name }}"></i>\n')

        with open(os.path.join(temp_dir, "guard_wrapper.html"), "w") as file:
            file.write(
                '<div id="{{ id }}" title="{{ evil }}">{{ content }}'
                '<Icon id="tail-1" name="chevron"/></div>\n'
            )

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        # Shaped exactly like a real placeholder token (marker, digit, marker).
        adversarial_evil = f"{_SLOT_PLACEHOLDER_CHAR}0{_SLOT_PLACEHOLDER_CHAR}"
        safe_evil = "SAFE"

        adversarial_rendered = renderer.render(
            f'<GuardWrapper id="w1" evil="{adversarial_evil}">'
            '<Leaf id="c1" text="Hello there"/>'
            "</GuardWrapper>"
        )
        baseline_rendered = renderer.render(
            f'<GuardWrapper id="w1" evil="{safe_evil}">'
            '<Leaf id="c1" text="Hello there"/>'
            "</GuardWrapper>"
        )

        # The marker's presence must not corrupt or omit anything: swapping
        # the adversarial value back out for the safe one must reproduce the
        # baseline render exactly (real Leaf content intact, Icon expanded).
        assert (
            adversarial_rendered.replace(adversarial_evil, safe_evil)
            == baseline_rendered
        )
        # And the marker-shaped attribute value must survive untouched, not
        # be misinterpreted as (or replaced by) a restored slot value.
        assert adversarial_evil in adversarial_rendered
        assert '<span id="c1" text="Hello there">Hello there</span>' in adversarial_rendered
        assert '<i id="tail-1" class="icon-chevron" name="chevron"></i>' in adversarial_rendered


def test_nested_opacified_slot_seen_as_placeholder_by_own_template():
    """Documents the known, accepted remaining gap in the opacify/restore
    optimization (see the "emit-vs-inspect" note on
    `_collect_opacifiable_slot_values`): the fix closes the gap for a
    component's own direct emit-and-inspect of its own slot value, but NOT
    for a value passed further into a nested custom tag's own template.

    Here, the outer wrapper emits its `content` slot value straight into a
    nested `<Inspector>` tag (`<Inspector>{{ content }}</Inspector>`).
    Because substitution happens once, at the level of the component whose
    context originally held the value (the outer wrapper), what actually
    reaches `Inspector`'s own template is the short placeholder token, not
    the real HTML -- so `Inspector`'s own `{{ content|length }}` sees the
    token's length, not the real content's length.

    This test pins that CURRENT, documented behavior. It is intentionally
    narrower in scope than the fully-fixed direct case (see
    test_opacified_slot_length_check_sees_real_content_not_placeholder and
    test_opacified_slot_can_both_emit_and_inspect_the_same_value above,
    which continue to guard against regressing to the old, fully-broken
    behavior for that direct case). Per the reviewer's own recommendation,
    this narrower gap is not being closed here -- doing so would require
    detecting "value emitted inside a nested custom tag" during
    substitution, adding real complexity for a rare case.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "nested_gap_child.html"), "w") as file:
            file.write('<span id="{{ id }}">{{ text }}</span>\n')

        with open(os.path.join(temp_dir, "inspector.html"), "w") as file:
            file.write('<b id="{{ id }}">{{ content }}|{{ content|length }}</b>\n')

        with open(os.path.join(temp_dir, "nested_gap_wrapper.html"), "w") as file:
            file.write(
                '<div id="{{ id }}"><Inspector id="insp-1">{{ content }}'
                "</Inspector></div>\n"
            )

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render(
            '<NestedGapWrapper id="w1">'
            '<NestedGapChild id="c1" text="Hello there"/>'
            "</NestedGapWrapper>"
        )

        real_child_html = '<span id="c1" text="Hello there">Hello there</span>'
        # The real HTML DOES eventually appear in the final output -- the
        # placeholder token Inspector re-emits gets restored at the outer
        # wrapper's own level, after Inspector's template has already
        # rendered against it -- so emitting still works end-to-end.
        assert real_child_html in rendered
        # But Inspector's own `{{ content|length }}` saw the short
        # placeholder token's length, not the real child HTML's length:
        # this is the documented, accepted gap.
        assert str(len(real_child_html)) not in rendered
        assert f"{real_child_html}|3" in rendered
