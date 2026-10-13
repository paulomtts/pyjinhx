"""PJXRosterChip — one selected roster entry rendered as a chip with a hidden input."""

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from pyjinhx import discovery
from pyjinhx._component import _is_slot_field
from pyjinhx.builtins.ui.pjx_roster_chip import PJXRosterChip
from pyjinhx.classless import component
from pyjinhx.rendering import render

PACKAGE_DIR = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_roster_chip"
)
OPTIONAL_FIELDS = [
    "initials",
    "color",
    "src",
    "icon",
    "extra",
    "detail",
    "class_name",
]
TEXT_FIELDS = [
    "value",
    "label",
    "initials",
    "color",
    "src",
    "icon",
    "name",
    "remove_label",
]


def _chip(parse_html, session, **kwargs):
    """Render one chip (value/label default to u1/Ada) and return its single root."""
    kwargs.setdefault("value", "u1")
    kwargs.setdefault("label", "Ada")
    roots = parse_html(render(PJXRosterChip(**kwargs), session))
    assert len(roots) == 1
    return roots[0]


def _by_class(root, name):
    return [el for el in root.descendants() if name in el.classes]


def _one(root, name):
    found = _by_class(root, name)
    assert len(found) == 1, name
    return found[0]


@pytest.fixture
def host_dir(tmp_path: Path):
    """A components root holding a host template that mounts the chip by tag."""
    (tmp_path / "roster_host.pjx").write_text(
        '<div id="{{ id }}" class="host"><PJXRosterChip value="u1" label="Ada"/></div>'
    )
    discovery.build_registry(tmp_path, [PJXRosterChip])
    yield tmp_path
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def test_required_fields_only_gives_the_documented_defaults():
    chip = PJXRosterChip(value="u1", label="Ada")

    assert chip.value == "u1"
    assert chip.label == "Ada"
    assert chip.name == ""
    assert chip.remove_label == "Remove"
    assert chip.disabled is False
    for field in OPTIONAL_FIELDS:
        assert getattr(chip, field) == "", field
    assert chip.extra_attrs == {}


@pytest.mark.parametrize("field", ["value", "label"])
def test_missing_value_or_label_raises_naming_the_field(field):
    kwargs = {"value": "u1", "label": "Ada"}
    del kwargs[field]

    with pytest.raises(ValidationError) as exc_info:
        PJXRosterChip(**kwargs)

    assert exc_info.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize("field", ["value", "label"])
def test_empty_value_or_label_raises_naming_the_field(field):
    kwargs = {"value": "u1", "label": "Ada", field: ""}

    with pytest.raises(ValidationError) as exc_info:
        PJXRosterChip(**kwargs)

    assert exc_info.value.errors()[0]["loc"] == (field,)


def test_color_with_a_double_quote_raises_at_construction():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterChip(value="u1", label="Ada", color='red"')

    assert exc_info.value.errors()[0]["loc"] == ("color",)


def test_extra_attrs_with_a_bad_name_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterChip(value="u1", label="Ada", extra_attrs={"bad name": "x"})

    assert exc_info.value.errors()[0]["loc"] == ("extra_attrs",)


@pytest.mark.parametrize("field", ["extra", "detail"])
def test_extra_and_detail_are_slot_fields(field):
    assert _is_slot_field(PJXRosterChip, field)


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_text_fields_are_not_slot_fields(field):
    assert not _is_slot_field(PJXRosterChip, field)


def test_root_is_one_div_carrying_id_classes_marker_and_extra_attrs(
    parse_html, session
):
    root = _chip(
        parse_html,
        session,
        id="chip-1",
        class_name="mine",
        extra_attrs={"data-team": "core"},
    )

    assert root.tag == "div"
    assert root.attrs["id"] == "chip-1"
    assert "pjx-roster-picker__chip" in root.classes
    assert "mine" in root.classes
    assert "data-pjx-roster-chip" in root.attrs
    assert root.attrs["data-team"] == "core"


def test_extra_attrs_do_not_disturb_the_hidden_inputs_name_and_value(
    parse_html, session
):
    root = _chip(
        parse_html,
        session,
        name="members",
        extra_attrs={"name": "x", "value": "y"},
    )

    hidden = root.children[0]
    assert hidden.attrs["name"] == "members"
    assert hidden.attrs["value"] == "u1"


def test_hidden_input_is_the_roots_first_child(parse_html, session):
    root = _chip(parse_html, session, name="members")

    hidden = root.children[0]
    assert hidden.tag == "input"
    assert hidden.attrs["type"] == "hidden"
    assert "pjx-roster-picker__chip-input" in hidden.classes
    assert hidden.attrs["name"] == "members"
    assert hidden.attrs["value"] == "u1"


def test_empty_name_still_emits_an_empty_name_attribute(parse_html, session):
    root = _chip(parse_html, session)

    hidden = root.children[0]
    assert "name" in hidden.attrs
    assert hidden.attrs["name"] == ""


def test_top_row_holds_avatar_label_and_remove_button_in_order(parse_html, session):
    root = _chip(parse_html, session)

    assert len(root.children) == 2
    row = root.children[1]
    assert row.tag == "div"
    assert "pjx-roster-picker__chip-row" in row.classes
    avatar, label, button = row.children
    assert "pjx-roster-picker__chip-avatar" in avatar.classes
    assert label.tag == "span"
    assert "pjx-roster-picker__chip-label" in label.classes
    assert label.text == "Ada"
    assert button.tag == "button"
    assert "pjx-roster-picker__chip-remove" in button.classes


def test_remove_button_is_a_labelled_icon_button(parse_html, session):
    root = _chip(parse_html, session)

    button = _one(root, "pjx-roster-picker__chip-remove")
    assert button.attrs["type"] == "button"
    assert "data-pjx-roster-remove" in button.attrs
    assert button.attrs["aria-label"] == "Remove: Ada"
    (icon,) = button.children
    assert icon.tag == "svg"
    assert icon.attrs["aria-hidden"] == "true"


def test_remove_label_replaces_the_aria_label_prefix(parse_html, session):
    root = _chip(parse_html, session, remove_label="Tirar")

    button = _one(root, "pjx-roster-picker__chip-remove")
    assert button.attrs["aria-label"] == "Tirar: Ada"


def test_without_icon_the_visual_is_a_small_avatar_with_a_decorative_image(
    parse_html, session
):
    root = _chip(parse_html, session, src="/a.png")

    avatar = _one(root, "pjx-roster-picker__chip-avatar")
    assert "pjx-avatar" in avatar.classes
    assert "pjx-avatar--sm" in avatar.classes
    (img,) = [el for el in avatar.descendants() if el.tag == "img"]
    assert img.attrs["src"] == "/a.png"
    assert img.attrs["alt"] == ""


def test_avatar_shows_initials_and_color_when_there_is_no_src(parse_html, session):
    root = _chip(parse_html, session, initials="AL", color="#ff0000")

    avatar = _one(root, "pjx-roster-picker__chip-avatar")
    assert avatar.attrs["style"] == "background:#ff0000;"
    assert _one(avatar, "pjx-avatar__initials").text == "AL"


def test_icon_replaces_the_avatar_even_with_src_and_initials(parse_html, session):
    root = _chip(parse_html, session, icon="user", src="/a.png", initials="AL")

    visual = root.children[1].children[0]
    assert visual.tag == "svg"
    assert "pjx-roster-picker__chip-icon" in visual.classes
    assert _by_class(root, "pjx-avatar") == []
    assert [el for el in root.descendants() if el.tag == "img"] == []


def test_unknown_icon_renders_a_hidden_placeholder_and_logs(
    parse_html, session, caplog
):
    with caplog.at_level(logging.WARNING):
        root = _chip(parse_html, session, icon="no-such-icon")

    visual = root.children[1].children[0]
    assert visual.tag == "span"
    assert "hidden" in visual.attrs
    assert _by_class(root, "pjx-avatar") == []
    assert _one(root, "pjx-roster-picker__chip-label").text == "Ada"
    assert "unknown icon name" in caplog.text


def test_two_chips_in_one_session_never_share_an_id(parse_html, session):
    html = render(PJXRosterChip(value="u1", label="Ada"), session) + render(
        PJXRosterChip(value="u2", label="Bob"), session
    )

    roots = parse_html(html)
    ids = [
        el.attrs["id"]
        for root in roots
        for el in [root, *root.descendants()]
        if "id" in el.attrs
    ]
    # Each chip carries three ids: its root, its avatar and its remove icon.
    assert len(ids) == 6
    assert len(set(ids)) == 6


def test_package_ships_no_css_or_js():
    assert PACKAGE_DIR.is_dir()
    assert list(PACKAGE_DIR.glob("*.css")) == []
    assert list(PACKAGE_DIR.glob("*.js")) == []


def test_tag_in_a_host_template_renders_the_chip(host_dir, parse_html, session):
    host = component("RosterHost", template_dir=host_dir)

    (root,) = parse_html(render(host(id="h"), session))  # pyright: ignore[reportCallIssue]

    (chip,) = root.children
    assert "pjx-roster-picker__chip" in chip.classes
    assert chip.children[0].attrs["value"] == "u1"
    assert _one(chip, "pjx-roster-picker__chip-label").text == "Ada"
