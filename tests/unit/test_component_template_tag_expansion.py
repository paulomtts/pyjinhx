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
    """Regression guard for the `not value` guard inside
    `_opacify_expanded_slots.opacify()`: an empty slot value must stay
    falsy after passing through the opacify fast path, so a template's
    `{% if slot %}` truthiness check isn't flipped from falsy to truthy by
    a non-empty placeholder token. A prior implementer discovered this only
    via golden-file tests (lazy_load, accordion, tabs, ...) not covered by
    this diff; this test would fail if the `not value` guard were removed.
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


def test_opacified_slot_length_check_sees_placeholder_not_real_content_known_limitation():
    """Documents the emit-only invariant described in
    `_opacify_expanded_slots`'s docstring (KNOWN LIMITATION): a template
    that *inspects* an opacified slot value (here, via `|length`) sees the
    short placeholder token, not the real already-expanded HTML, because
    the opacify substitution happens before `template.render()` runs.

    This is the current, accepted, documented behavior -- NOT what a naive
    reader would expect -- so this test asserts the observed (placeholder)
    length, proving the trade-off is understood and pinning it so it can't
    silently change without this test failing.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "child.html"), "w") as file:
            file.write('<span id="{{ id }}">{{ text }}</span>\n')

        with open(os.path.join(temp_dir, "wrapper.html"), "w") as file:
            file.write('<div id="{{ id }}">{{ content|length }}</div>\n')

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render(
            '<Wrapper id="w1"><Child id="c1" text="Hello there"/></Wrapper>'
        )

        real_child_html = '<span id="c1" text="Hello there">Hello there</span>'
        # The real, already-expanded child HTML is far longer than the
        # single-digit placeholder token length the template actually sees.
        assert len(real_child_html) > 9
        assert rendered == "<div id=\"w1\">3</div>"


def test_list_slot_values_recurse_through_opacify_and_restore_correctly():
    """`_opacify_expanded_slots` recurses into list-shaped slot values (the
    same shape `base._wrap_slot_value` produces for a field like
    `PJXDropdown.items: list[str | BaseComponent]`). Exercise a slot field
    that's a `list[str]` with a mix of:
    - an already-fully-expanded value containing no tag-looking substring
      (opacified, then restored via its placeholder token), and
    - a literal value containing a real custom tag (left alone by
      `opacify`, so it still gets expanded via the full `expand_custom_tags`
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
