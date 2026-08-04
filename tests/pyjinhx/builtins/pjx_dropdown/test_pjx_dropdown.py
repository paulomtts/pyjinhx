"""PJXDropdown renders a trigger button over a hidden menu panel wired to the popover runtime (port of v0.x pyjinhx/builtins/ui/pjx_dropdown/pjx_dropdown.py)."""

import dataclasses

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_dropdown import PJXDropdown
from pyjinhx._component import BaseComponent, Slot
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession, accumulate_assets


@pytest.fixture
def dropdown_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXDropdown(id="d", **kw), session)


def test_default_render_is_a_start_aligned_root_with_trigger_and_menu(dropdown_session):
    assert _html(dropdown_session) == (
        '<div id="d" class="pjx-dropdown" data-pjx-popover>'
        '<button id="d-trigger" class="pjx-dropdown__trigger" type="button"'
        ' aria-expanded="false" aria-haspopup="menu" aria-controls="d-menu"'
        ' data-pjx-toggle="d-menu"></button>'
        '<div id="d-menu" class="pjx-dropdown__menu" data-pjx-popover-panel'
        ' role="menu" aria-label="Submenu" hidden></div>'
        "</div>"
    )


def test_align_start_matches_the_default(dropdown_session):
    assert _html(dropdown_session, align="start") == _html(dropdown_session)


def test_align_end_adds_the_alignment_modifier(dropdown_session):
    assert 'class="pjx-dropdown pjx-dropdown--align-end"' in _html(
        dropdown_session, align="end"
    )


def test_class_name_appended_to_root(dropdown_session):
    assert 'class="pjx-dropdown mine"' in _html(dropdown_session, class_name="mine")


def test_menu_label_lands_on_the_panel_aria_label(dropdown_session):
    assert 'aria-label="Actions"' in _html(dropdown_session, menu_label="Actions")


def test_string_trigger_is_interpolated(dropdown_session):
    assert ">Open</button>" in _html(dropdown_session, trigger="Open")


class DropdownChild(BaseComponent):
    """A minimal component child, to prove a nested component renders in a slot."""

    content: Slot = ""


@pytest.fixture
def dropdown_child_template(tmp_path):
    """Give DropdownChild a real template on disk and repoint its descriptor at it."""
    path = tmp_path / "dropdown_child.pjx"
    path.write_text('<span id="{{ id }}" class="child">{{ content }}</span>')
    DropdownChild.__pjx_descriptor__ = dataclasses.replace(
        DropdownChild.__pjx_descriptor__, template_path=path
    )
    yield path


def test_component_trigger_renders_inside_the_button(
    dropdown_session, dropdown_child_template
):
    html = _html(dropdown_session, trigger=DropdownChild(id="t", content="Menu"))
    assert '<span id="t" class="child">Menu</span></button>' in html


def test_items_render_in_order_inside_the_menu(
    dropdown_session, dropdown_child_template
):
    html = _html(
        dropdown_session,
        items=["First", DropdownChild(id="i2", content="Second")],
        menu_label="Actions",
    )
    body = html.split('aria-label="Actions" hidden>')[1].split("</div>")[0]
    assert body.startswith("First")
    assert '<span id="i2" class="child">Second</span>' in html
    assert body.index("First") < body.index("Second")


def test_empty_items_render_an_empty_menu(dropdown_session):
    assert 'aria-label="Submenu" hidden></div>' in _html(dropdown_session)


def test_invalid_align_is_rejected():
    with pytest.raises(ValidationError):
        PJXDropdown(id="d", align="middle")  # type: ignore[arg-type]


def test_dropped_behavior_field_is_rejected():
    """`behavior` did not survive the v2 port; extra="forbid" turns it into an error."""
    with pytest.raises(ValidationError):
        PJXDropdown(id="d", behavior=True)  # type: ignore[call-arg]


def test_dropped_extra_attrs_field_is_rejected():
    """`extra_attrs` did not survive the v2 port either (ADR 0006, strict core)."""
    with pytest.raises(ValidationError):
        PJXDropdown(id="d", extra_attrs={"data-x": "1"})  # type: ignore[call-arg]


def test_dropped_js_field_is_rejected():
    """`js` manual asset injection is gone; assets come from discovery alone."""
    with pytest.raises(ValidationError):
        PJXDropdown(id="d", js=["x.js"])  # type: ignore[call-arg]


def test_css_is_own_and_js_is_inherited_from_the_popover_ancestor():
    """The stylesheet is the dropdown's own; the runtime comes from the PJXPopover it extends.

    Replaces test_css_is_discovered_and_no_js_ships_with_the_component, whose
    `js_paths == ()` assertion encoded the #695 bug: the popover runtime never
    reached a session that rendered a dropdown.
    """
    descriptor = PJXDropdown.__pjx_descriptor__
    assert [p.name for p in descriptor.css_paths] == ["pjx_dropdown.css"]
    assert [p.name for p in descriptor.js_paths] == ["pjx_popover.js"]


def test_rendering_accumulates_the_popover_runtime_into_the_session():
    """A rendered dropdown puts pjx_popover.js into the session, which is what ships it to the page.

    Session-scoped accumulation, not registry-wide all_assets(): only a
    component that actually rendered may contribute an asset to a response.
    RenderSession does not auto-subscribe accumulate_assets, so the test
    subscribes it exactly as the framework's own callers do.
    """
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)

    render(PJXDropdown(id="d", trigger="Actions"), session)

    assert sorted(p.name for p in session.js_assets) == ["pjx_popover.js"]
    assert sorted(p.name for p in session.css_assets) == ["pjx_dropdown.css"]


def test_a_component_item_renders_its_markup_unescaped(
    dropdown_session, dropdown_child_template
):
    """Markup in the menu must arrive as a component: list-slot components are opaque nodes."""
    html = _html(
        dropdown_session, items=[DropdownChild(id="i1", content="<b>Edit</b>")]
    )
    assert '<span id="i1" class="child"><b>Edit</b></span>' in html
    assert "&lt;span" not in html


def test_a_str_item_is_escaped_plain_text_on_purpose(dropdown_session):
    """A raw-HTML string item is data, not markup — it renders escaped, by design.

    ADR 0003 makes the *slot's own* string form raw-HTML-capable, but a list
    entry is a collection member, so render_context._wrap_slot_value leaves it
    to Jinja's autoescape. This is the documented contract, not the #695 bug:
    the bug was docs/demos/interaction.py passing markup where text is meant.
    """
    html = _html(dropdown_session, items=["<button>Edit</button>"])
    assert "&lt;button&gt;Edit&lt;/button&gt;" in html
    assert "<button>Edit</button>" not in html
