"""PJXRosterResults — one page of roster picker search results."""

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from pyjinhx._component import _is_slot_field
from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.builtins.ui.pjx_roster_picker import PJXRosterItem
from pyjinhx.builtins.ui.pjx_roster_results import PJXRosterResults
from pyjinhx.rendering import render

PACKAGE_DIR = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_roster_results"
)
TEXT_FIELDS = [
    "picker_id",
    "next_url",
    "next_cursor",
    "empty_message",
    "remove_label",
]


def _items(*values):
    return [PJXRosterItem(value=value, label=value.upper()) for value in values]


def _results(parse_html, session, **kwargs):
    """Render one results page (picker_id defaults to p1) and return its single root."""
    kwargs.setdefault("picker_id", "p1")
    roots = parse_html(render(PJXRosterResults(**kwargs), session))
    assert len(roots) == 1
    return roots[0]


def _by_class(root, name):
    return [el for el in root.descendants() if name in el.classes]


def _one(root, name):
    found = _by_class(root, name)
    assert len(found) == 1, name
    return found[0]


# ── Props and validation ─────────────────────────────────────────────────────


def test_required_fields_only_gives_the_documented_defaults():
    results = PJXRosterResults(picker_id="p1")

    assert results.picker_id == "p1"
    assert results.items == []
    assert results.next_url == ""
    assert results.next_cursor == ""
    assert results.empty_message == "No results"
    assert results.remove_label == "Remove"
    assert results.class_name == ""
    assert results.extra_attrs == {}


def test_missing_picker_id_raises_naming_the_field():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterResults()  # pyright: ignore[reportCallIssue]

    assert exc_info.value.errors()[0]["loc"] == ("picker_id",)


@pytest.mark.parametrize("picker_id", ["", "p 1", "p\t1", "p1\n"])
def test_empty_or_whitespace_picker_id_raises_naming_the_field(picker_id):
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterResults(picker_id=picker_id)

    assert exc_info.value.errors()[0]["loc"] == ("picker_id",)


def test_class_name_with_a_double_quote_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterResults(picker_id="p1", class_name='a"b')

    assert exc_info.value.errors()[0]["loc"] == ("class_name",)


def test_extra_attrs_with_a_bad_name_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterResults(picker_id="p1", extra_attrs={"bad name": "x"})

    assert exc_info.value.errors()[0]["loc"] == ("extra_attrs",)


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_text_props_are_not_slot_fields(field):
    assert not _is_slot_field(PJXRosterResults, field)


# ── Markup ───────────────────────────────────────────────────────────────────


def test_root_is_one_div_carrying_id_classes_marker_and_extra_attrs(
    parse_html, session
):
    root = _results(
        parse_html,
        session,
        id="page-1",
        class_name="mine",
        extra_attrs={"data-team": "core"},
    )

    assert root.tag == "div"
    assert root.attrs["id"] == "page-1"
    assert "pjx-roster-picker__results-page" in root.classes
    assert "mine" in root.classes
    assert "data-pjx-roster-results" in root.attrs
    assert root.attrs["data-team"] == "core"


def test_package_ships_no_css_or_js():
    assert PACKAGE_DIR.is_dir()
    assert list(PACKAGE_DIR.glob("*.css")) == []
    assert list(PACKAGE_DIR.glob("*.js")) == []


def _pick_rows(root):
    return [el for el in root.children if el.tag == "button"]


def _templates(root):
    return [el for el in root.children if el.tag == "template"]


def test_each_item_renders_a_pick_button_then_a_template_in_order(parse_html, session):
    root = _results(parse_html, session, items=_items("u1", "u2"))

    assert [el.tag for el in root.children] == [
        "button",
        "template",
        "button",
        "template",
    ]
    assert [b.attrs["data-value"] for b in _pick_rows(root)] == ["u1", "u2"]


def test_pick_button_is_a_non_submitting_marked_button_carrying_the_value(
    parse_html, session
):
    root = _results(parse_html, session, items=_items("u1"))

    (button,) = _pick_rows(root)
    assert button.attrs["type"] == "button"
    assert "pjx-roster-picker__pick" in button.classes
    assert "data-pjx-roster-pick" in button.attrs
    assert button.attrs["data-value"] == "u1"


def test_pick_button_holds_avatar_text_and_plus_icon_in_order(parse_html, session):
    items = [PJXRosterItem(value="u1", label="Ada", src="/a.png")]

    root = _results(parse_html, session, items=items)

    (button,) = _pick_rows(root)
    avatar, text, add = button.children
    assert "pjx-avatar" in avatar.classes
    assert "pjx-avatar--sm" in avatar.classes
    assert "pjx-roster-picker__pick-avatar" in avatar.classes
    (img,) = [el for el in avatar.descendants() if el.tag == "img"]
    assert img.attrs["src"] == "/a.png"
    assert img.attrs["alt"] == ""
    assert text.tag == "span"
    assert "pjx-roster-picker__pick-text" in text.classes
    assert add.tag == "svg"
    assert add.attrs["aria-hidden"] == "true"
    assert "pjx-roster-picker__pick-add" in add.classes


def test_text_span_holds_label_then_subtitle(parse_html, session):
    items = [PJXRosterItem(value="u1", label="Ada", subtitle="Engineering")]

    root = _results(parse_html, session, items=items)

    text = _one(root, "pjx-roster-picker__pick-text")
    label, subtitle = text.children
    assert "pjx-roster-picker__pick-label" in label.classes
    assert label.text == "Ada"
    assert "pjx-roster-picker__pick-subtitle" in subtitle.classes
    assert subtitle.text == "Engineering"


def test_empty_subtitle_renders_no_subtitle_span(parse_html, session):
    root = _results(parse_html, session, items=_items("u1"))

    (label,) = _one(root, "pjx-roster-picker__pick-text").children
    assert "pjx-roster-picker__pick-label" in label.classes
    assert _by_class(root, "pjx-roster-picker__pick-subtitle") == []


def test_icon_replaces_the_avatar_even_with_src_and_initials(parse_html, session):
    items = [
        PJXRosterItem(value="u1", label="Ada", icon="user", src="/a.png", initials="AL")
    ]

    root = _results(parse_html, session, items=items)

    (button,) = _pick_rows(root)
    visual = button.children[0]
    assert visual.tag == "svg"
    assert "pjx-roster-picker__pick-icon" in visual.classes
    assert [el for el in button.descendants() if "pjx-avatar" in el.classes] == []
    assert [el for el in button.descendants() if el.tag == "img"] == []


def test_unknown_icon_logs_and_still_renders_the_label(parse_html, session, caplog):
    items = [PJXRosterItem(value="u1", label="Ada", icon="no-such-icon")]

    with caplog.at_level(logging.WARNING):
        root = _results(parse_html, session, items=items)

    (button,) = _pick_rows(root)
    visual = button.children[0]
    assert visual.tag == "span"
    assert "hidden" in visual.attrs
    assert _one(button, "pjx-roster-picker__pick-label").text == "Ada"
    assert "unknown icon name" in caplog.text


def test_pick_button_shows_neither_extra_nor_detail(parse_html, session):
    items = [
        PJXRosterItem(value="u1", label="Ada", extra="<b>admin</b>", detail="<i>x</i>")
    ]

    root = _results(parse_html, session, items=items)

    (button,) = _pick_rows(root)
    assert [el for el in button.descendants() if el.tag in ("b", "i")] == []
    assert [
        el
        for el in button.descendants()
        if "pjx-roster-picker__chip-extra" in el.classes
    ] == []


# ── Template chip ────────────────────────────────────────────────────────────


def test_template_holds_one_full_unnamed_chip(parse_html, session):
    root = _results(parse_html, session, items=_items("u1"))

    (template,) = _templates(root)
    (chip,) = template.children
    assert "pjx-roster-picker__chip" in chip.classes
    assert "data-pjx-roster-chip" in chip.attrs
    hidden = chip.children[0]
    assert hidden.tag == "input"
    assert hidden.attrs["type"] == "hidden"
    assert hidden.attrs["name"] == ""
    assert hidden.attrs["value"] == "u1"
    assert _one(chip, "pjx-roster-picker__chip-label").text == "U1"
    button = _one(chip, "pjx-roster-picker__chip-remove")
    assert "data-pjx-roster-remove" in button.attrs
    assert button.attrs["aria-label"] == "Remove: U1"


def test_remove_label_replaces_the_chip_aria_label_prefix(parse_html, session):
    root = _results(parse_html, session, items=_items("u1"), remove_label="Tirar")

    (template,) = _templates(root)
    button = _one(template, "pjx-roster-picker__chip-remove")
    assert button.attrs["aria-label"] == "Tirar: U1"


def test_chip_carries_visual_extra_and_detail_but_no_subtitle(parse_html, session):
    items = [
        PJXRosterItem(
            value="u1",
            label="Ada",
            subtitle="Engineering",
            icon="user",
            extra="<b>admin</b>",
            detail="<i>x</i>",
        )
    ]

    root = _results(parse_html, session, items=items)

    (template,) = _templates(root)
    chip = template.children[0]
    _one(chip, "pjx-roster-picker__chip-icon")
    assert _by_class(chip, "pjx-avatar") == []
    (bold,) = _one(chip, "pjx-roster-picker__chip-extra").children
    assert bold.tag == "b"
    assert bold.text == "admin"
    (italic,) = _one(chip, "pjx-roster-picker__chip-detail").children
    assert italic.tag == "i"
    assert all("Engineering" not in el.text for el in [chip, *chip.descendants()])


def test_chip_avatar_mirrors_the_items_src(parse_html, session):
    items = [PJXRosterItem(value="u1", label="Ada", src="/a.png")]

    root = _results(parse_html, session, items=items)

    (template,) = _templates(root)
    avatar = _one(template, "pjx-roster-picker__chip-avatar")
    (img,) = [el for el in avatar.descendants() if el.tag == "img"]
    assert img.attrs["src"] == "/a.png"


def test_a_component_in_extra_renders_as_markup_in_the_chip(parse_html, session):
    items = [
        PJXRosterItem(
            value="u1", label="Ada", extra=PJXIcon(name="user", class_name="role-icon")
        )
    ]

    root = _results(parse_html, session, items=items)

    (template,) = _templates(root)
    (icon,) = _one(template, "pjx-roster-picker__chip-extra").children
    assert icon.tag == "svg"
    assert "role-icon" in icon.classes


def test_duplicate_values_render_every_row_with_unique_ids(parse_html, session):
    root = _results(parse_html, session, items=_items("u1", "u1"))

    assert [b.attrs["data-value"] for b in _pick_rows(root)] == ["u1", "u1"]
    assert len(_templates(root)) == 2
    ids = [el.attrs["id"] for el in [root, *root.descendants()] if "id" in el.attrs]
    assert len(ids) == len(set(ids))


# ── Escaping (rows and chips) ────────────────────────────────────────────────


def test_markup_in_label_and_subtitle_is_text_not_a_tag(parse_html, session):
    label = "<script>alert(1)</script>"
    subtitle = "<script>alert(2)</script>"
    items = [PJXRosterItem(value="u1", label=label, subtitle=subtitle)]

    root = _results(parse_html, session, items=items)

    assert [el for el in root.descendants() if el.tag == "script"] == []
    assert _one(root, "pjx-roster-picker__pick-label").text == label
    assert _one(root, "pjx-roster-picker__pick-subtitle").text == subtitle
    (template,) = _templates(root)
    assert _one(template, "pjx-roster-picker__chip-label").text == label


def test_row_text_is_escaped_exactly_once(parse_html, session):
    items = [PJXRosterItem(value="u1", label="A & B", subtitle="<", initials="<")]

    root = _results(parse_html, session, items=items)

    (button,) = _pick_rows(root)
    assert _one(button, "pjx-roster-picker__pick-label").text == "A & B"
    assert _one(button, "pjx-roster-picker__pick-subtitle").text == "<"
    assert _one(button, "pjx-avatar__initials").text == "<"
    (template,) = _templates(root)
    assert _one(template, "pjx-roster-picker__chip-label").text == "A & B"


# ── Sentinel ─────────────────────────────────────────────────────────────────


def test_items_and_next_url_close_the_page_with_a_scoped_sentinel(parse_html, session):
    root = _results(
        parse_html,
        session,
        items=_items("u1"),
        next_url="/people?cursor=c2",
        next_cursor="c2",
    )

    sentinel = root.children[-1]
    assert sentinel.tag == "div"
    assert "data-pjx-lazy-load" in sentinel.attrs
    assert "pjx-roster-picker__more" in sentinel.classes
    assert sentinel.attrs["id"] == "p1-more-c2"
    assert sentinel.attrs["hx-get"] == "/people?cursor=c2"
    assert sentinel.attrs["hx-trigger"] == "intersect once root:#p1-results"
    assert sentinel.attrs["hx-swap"] == "outerHTML"


def test_sentinel_id_without_a_cursor_is_picker_id_more(parse_html, session):
    root = _results(parse_html, session, items=_items("u1"), next_url="/people")

    assert root.children[-1].attrs["id"] == "p1-more"


def test_no_next_url_renders_no_sentinel(parse_html, session):
    root = _results(parse_html, session, items=_items("u1"), next_cursor="c2")

    assert [el for el in root.descendants() if "data-pjx-lazy-load" in el.attrs] == []


def test_no_items_with_a_next_url_renders_no_sentinel(parse_html, session):
    root = _results(parse_html, session, next_url="/people", next_cursor="c2")

    assert [el for el in root.descendants() if "data-pjx-lazy-load" in el.attrs] == []


# ── Empty state ──────────────────────────────────────────────────────────────


def test_no_items_renders_only_the_empty_message(parse_html, session):
    root = _results(parse_html, session)

    (empty,) = root.children
    assert empty.tag == "p"
    assert "pjx-roster-picker__empty" in empty.classes
    assert empty.children == []
    assert empty.text == "No results"


def test_custom_empty_message_replaces_the_text(parse_html, session):
    root = _results(parse_html, session, empty_message="Nobody found")

    assert _one(root, "pjx-roster-picker__empty").text == "Nobody found"


def test_items_render_no_empty_message(parse_html, session):
    root = _results(parse_html, session, items=_items("u1"))

    assert _by_class(root, "pjx-roster-picker__empty") == []


def test_extra_attrs_land_on_the_root_only(parse_html, session):
    root = _results(
        parse_html,
        session,
        items=_items("u1"),
        next_url="/people",
        extra_attrs={"data-team": "core"},
    )

    assert root.attrs["data-team"] == "core"
    assert [el for el in root.descendants() if "data-team" in el.attrs] == []
    assert "data-pjx-lazy-load" in root.children[-1].attrs


# ── Escaping (empty state and sentinel) ──────────────────────────────────────


def test_empty_message_is_escaped_exactly_once(parse_html, session):
    root = _results(parse_html, session, empty_message="<b>A & B</b>")

    empty = _one(root, "pjx-roster-picker__empty")
    assert empty.children == []
    assert empty.text == "<b>A & B</b>"


def test_quotes_and_ampersands_in_attribute_props_round_trip(parse_html, session):
    items = [PJXRosterItem(value='a"&b', label="Ada")]

    root = _results(
        parse_html,
        session,
        items=items,
        remove_label='R"&x',
        next_url='/people?q=a&b="2"',
        next_cursor='c"&2',
    )

    (button,) = _pick_rows(root)
    assert button.attrs["data-value"] == 'a"&b'
    (template,) = _templates(root)
    chip = template.children[0]
    assert chip.children[0].attrs["value"] == 'a"&b'
    remove = _one(chip, "pjx-roster-picker__chip-remove")
    assert remove.attrs["aria-label"] == 'R"&x: Ada'
    sentinel = root.children[-1]
    assert sentinel.attrs["hx-get"] == '/people?q=a&b="2"'
    assert sentinel.attrs["id"] == 'p1-more-c"&2'


# ── Ids ──────────────────────────────────────────────────────────────────────


def test_two_pages_in_one_session_never_share_an_id(parse_html, session):
    html = render(
        PJXRosterResults(
            picker_id="p1",
            items=_items("u1", "u2"),
            next_url="/people?cursor=c1",
            next_cursor="c1",
        ),
        session,
    ) + render(
        PJXRosterResults(
            picker_id="p1",
            items=_items("u3"),
            next_url="/people?cursor=c2",
            next_cursor="c2",
        ),
        session,
    )

    roots = parse_html(html)
    ids = [
        el.attrs["id"]
        for root in roots
        for el in [root, *root.descendants()]
        if "id" in el.attrs
    ]
    assert "p1-more-c1" in ids
    assert "p1-more-c2" in ids
    assert len(ids) == len(set(ids))
