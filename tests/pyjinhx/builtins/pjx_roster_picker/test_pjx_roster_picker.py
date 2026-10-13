"""PJXRosterPicker — the picker shell: search combobox, chips, cap hint, validity input and CSS."""

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from pyjinhx import discovery
from pyjinhx._component import _is_slot_field
from pyjinhx.builtins.ui.pjx_roster_picker import PJXRosterItem, PJXRosterPicker
from pyjinhx.classless import component
from pyjinhx.rendering import render
from pyjinhx.session import accumulate_assets

PACKAGE_DIR = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_roster_picker"
)
CSS_PATH = PACKAGE_DIR / "pjx_roster_picker.css"
JS_PATH = PACKAGE_DIR / "pjx_roster_picker.js"

TEXT_FIELDS = [
    "name",
    "candidates_url",
    "placeholder",
    "remove_label",
    "limit_label",
    "empty_message",
    "class_name",
]

CSS_CLASSES = [
    "pjx-roster-picker",
    "pjx-roster-picker__search",
    "pjx-roster-picker__input",
    "pjx-roster-picker__results",
    "pjx-roster-picker__results--above",
    "pjx-roster-picker__results-page",
    "pjx-roster-picker__pick",
    "pjx-roster-picker__pick-avatar",
    "pjx-roster-picker__pick-icon",
    "pjx-roster-picker__pick-text",
    "pjx-roster-picker__pick-label",
    "pjx-roster-picker__pick-subtitle",
    "pjx-roster-picker__pick-add",
    "pjx-roster-picker__empty",
    "pjx-roster-picker__more",
    "pjx-roster-picker__chips",
    "pjx-roster-picker__chip",
    "pjx-roster-picker__chip-row",
    "pjx-roster-picker__chip-label",
    "pjx-roster-picker__chip-extra",
    "pjx-roster-picker__chip-remove",
    "pjx-roster-picker__chip-detail",
    "pjx-roster-picker__chip-avatar",
    "pjx-roster-picker__chip-icon",
    "pjx-roster-picker__hint",
    "pjx-roster-picker--invalid",
    "pjx-roster-picker__validity",
]
# Tokens that name a colour, a radius or a shadow default to a semantic token;
# sizes and spacing have no semantic token to lean on, so they are literals.
SEMANTIC_TOKENS = {
    "--pjx-roster-picker-bg": "var(--surface",
    "--pjx-roster-picker-fg": "var(--text",
    "--pjx-roster-picker-muted": "var(--text-muted",
    "--pjx-roster-picker-border": "var(--border",
    "--pjx-roster-picker-focus": "var(--border-focus",
    "--pjx-roster-picker-radius": "var(--radius-md",
    "--pjx-roster-picker-chip-bg": "var(--surface-alt",
    "--pjx-roster-picker-results-bg": "var(--surface-alt",
    "--pjx-roster-picker-shadow": "var(--shadow-md",
    "--pjx-roster-picker-row-hover": "var(--surface-hover",
    "--pjx-roster-picker-row-active": "var(--accent-soft",
}
LITERAL_TOKENS = [
    "--pjx-roster-picker-padding",
    "--pjx-roster-picker-gap",
    "--pjx-roster-picker-z",
    "--pjx-roster-picker-max-h",
]


def _items(*values):
    return [PJXRosterItem(value=value, label=value.upper()) for value in values]


def _picker(parse_html, session, **kwargs):
    """Render one picker (name/candidates_url default to members//people) and return its single root."""
    kwargs.setdefault("name", "members")
    kwargs.setdefault("candidates_url", "/people")
    roots = parse_html(render(PJXRosterPicker(**kwargs), session))
    assert len(roots) == 1
    return roots[0]


def _by_class(root, name):
    return [el for el in root.descendants() if name in el.classes]


def _one(root, name):
    found = _by_class(root, name)
    assert len(found) == 1, name
    return found[0]


def _css():
    """The stylesheet with its comments stripped."""
    return re.sub(
        r"/\*.*?\*/", "", CSS_PATH.read_text(encoding="utf-8"), flags=re.DOTALL
    )


def _token_block():
    match = re.search(r":where\(:root\)\s*\{([^}]*)\}", _css())
    assert match is not None
    return dict(re.findall(r"(--pjx-roster-picker-[\w-]+)\s*:\s*([^;]+);", match[1]))


def _rules():
    """Every innermost (selector, body) pair, the token block left out.

    Brace-free selectors only match innermost blocks, so an @media wrapper
    never shows up as a selector; its inner rules do.
    """
    rules = []
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _css()):
        selector = selector.strip()
        if selector.startswith(":where(:root)"):
            continue
        rules.append((selector, body))
    return rules


@pytest.fixture
def host_dir(tmp_path: Path):
    """A components root holding a host template that mounts the picker by tag."""
    # Builtins are strict, so an undeclared inline attribute would be rejected;
    # extra_attrs arrives as JSON and is parsed by BaseComponent.
    (tmp_path / "roster_host.pjx").write_text(
        '<div id="{{ id }}" class="host"><PJXRosterPicker name="members"'
        ' candidates_url="/people" extra_attrs=\'{"data-team": "core"}\'/></div>'
    )
    discovery.build_registry(tmp_path, [PJXRosterPicker])
    yield tmp_path
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


# ── Props and validation ─────────────────────────────────────────────────────


def test_required_fields_only_gives_the_documented_defaults():
    picker = PJXRosterPicker(name="members", candidates_url="/people")

    assert picker.name == "members"
    assert picker.candidates_url == "/people"
    assert picker.items == []
    assert picker.max_items == 0
    assert picker.required is False
    assert picker.disabled is False
    assert picker.portal is False
    assert picker.placeholder == "Search…"
    assert picker.remove_label == "Remove"
    assert picker.limit_label == "Limit reached"
    assert picker.empty_message == "No results"
    assert picker.class_name == ""
    assert picker.extra_attrs == {}
    assert picker.chips == []


@pytest.mark.parametrize("field", ["name", "candidates_url"])
def test_missing_name_or_candidates_url_raises_naming_the_field(field):
    kwargs = {"name": "members", "candidates_url": "/people"}
    del kwargs[field]

    with pytest.raises(ValidationError) as exc_info:
        PJXRosterPicker(**kwargs)

    assert exc_info.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize("field", ["name", "candidates_url"])
def test_empty_name_or_candidates_url_raises_naming_the_field(field):
    kwargs = {"name": "members", "candidates_url": "/people", field: ""}

    with pytest.raises(ValidationError) as exc_info:
        PJXRosterPicker(**kwargs)

    assert exc_info.value.errors()[0]["loc"] == (field,)


def test_negative_max_items_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterPicker(name="members", candidates_url="/people", max_items=-1)

    assert exc_info.value.errors()[0]["loc"] == ("max_items",)


def test_duplicate_item_values_raise_naming_the_value():
    items = [
        PJXRosterItem(value="u1", label="Ada"),
        PJXRosterItem(value="u1", label="Bob"),
    ]

    with pytest.raises(ValidationError, match="'u1'"):
        PJXRosterPicker(name="members", candidates_url="/people", items=items)


def test_more_items_than_max_items_raises():
    with pytest.raises(ValidationError, match="max_items=2"):
        PJXRosterPicker(
            name="members",
            candidates_url="/people",
            items=_items("u1", "u2", "u3"),
            max_items=2,
        )


def test_items_equal_to_max_items_are_allowed():
    picker = PJXRosterPicker(
        name="members",
        candidates_url="/people",
        items=_items("u1", "u2"),
        max_items=2,
    )

    assert len(picker.chips) == 2


def test_zero_max_items_allows_any_count():
    picker = PJXRosterPicker(
        name="members",
        candidates_url="/people",
        items=_items(*[f"u{n}" for n in range(20)]),
    )

    assert len(picker.chips) == 20


def test_item_color_with_a_double_quote_raises_at_construction():
    items = [PJXRosterItem(value="u1", label="Ada", color='red"')]

    with pytest.raises(ValidationError, match="color"):
        PJXRosterPicker(name="members", candidates_url="/people", items=items)


def test_class_name_with_a_double_quote_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterPicker(name="members", candidates_url="/people", class_name='a"b')

    assert exc_info.value.errors()[0]["loc"] == ("class_name",)


def test_extra_attrs_with_a_bad_name_raises():
    with pytest.raises(ValidationError) as exc_info:
        PJXRosterPicker(
            name="members", candidates_url="/people", extra_attrs={"bad name": "x"}
        )

    assert exc_info.value.errors()[0]["loc"] == ("extra_attrs",)


def test_chips_is_a_slot_field():
    assert _is_slot_field(PJXRosterPicker, "chips")


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_text_props_are_not_slot_fields(field):
    assert not _is_slot_field(PJXRosterPicker, field)


# ── Markup contract ──────────────────────────────────────────────────────────


def test_root_is_one_div_carrying_id_classes_marker_and_data_attributes(
    parse_html, session
):
    root = _picker(parse_html, session, id="team", class_name="mine")

    assert root.tag == "div"
    assert root.attrs["id"] == "team"
    assert "pjx-roster-picker" in root.classes
    assert "mine" in root.classes
    assert "data-pjx-roster-picker" in root.attrs
    assert root.attrs["data-name"] == "members"
    assert root.attrs["data-max-items"] == "0"
    assert root.attrs["data-empty-message"] == "No results"
    assert "data-disabled" not in root.attrs
    assert "data-pjx-roster-picker-portal" not in root.attrs


def test_children_are_search_chips_hint_in_order(parse_html, session):
    root = _picker(parse_html, session)

    search, chips, hint = root.children
    assert search.tag == "div"
    assert "pjx-roster-picker__search" in search.classes
    assert chips.tag == "div"
    assert "pjx-roster-picker__chips" in chips.classes
    assert hint.tag == "p"
    assert "pjx-roster-picker__hint" in hint.classes


def test_search_input_carries_the_combobox_attributes(parse_html, session):
    root = _picker(parse_html, session, id="team", placeholder="Find people")

    search_input = _one(root, "pjx-roster-picker__input")
    results = _one(root, "pjx-roster-picker__results")
    assert search_input.tag == "input"
    assert search_input.attrs["type"] == "text"
    assert search_input.attrs["role"] == "combobox"
    assert search_input.attrs["aria-expanded"] == "false"
    assert search_input.attrs["aria-controls"] == results.attrs["id"]
    assert search_input.attrs["aria-autocomplete"] == "list"
    assert search_input.attrs["autocomplete"] == "off"
    assert search_input.attrs["name"] == "q"
    assert search_input.attrs["placeholder"] == "Find people"
    assert "aria-required" not in search_input.attrs


def test_search_input_is_wired_to_htmx(parse_html, session):
    root = _picker(parse_html, session, id="team")

    search_input = _one(root, "pjx-roster-picker__input")
    results = _one(root, "pjx-roster-picker__results")
    assert search_input.attrs["hx-get"] == "/people"
    assert (
        search_input.attrs["hx-trigger"]
        == "input delay:300ms, roster-picker-open delay:300ms"
    )
    assert search_input.attrs["hx-sync"] == "this:replace"
    assert search_input.attrs["hx-target"] == "#" + results.attrs["id"]
    assert search_input.attrs["hx-swap"] == "innerHTML"
    assert json.loads(search_input.attrs["hx-vals"]) == {"picker_id": "team"}


def test_search_input_form_names_no_element_in_the_render(parse_html, session):
    root = _picker(parse_html, session, items=_items("u1"))

    form_id = _one(root, "pjx-roster-picker__input").attrs["form"]
    assert form_id
    ids = [el.attrs.get("id") for el in [root, *root.descendants()]]
    assert form_id not in ids


def test_results_mount_is_hidden_and_empty_with_an_id_derived_from_the_picker(
    parse_html, session
):
    root = _picker(parse_html, session, id="team")

    results = _one(root, "pjx-roster-picker__results")
    assert results.tag == "div"
    assert results.attrs["id"] == "team-results"
    assert "hidden" in results.attrs
    assert results.children == []
    assert results.text.strip() == ""


def test_auto_generated_id_flows_into_results_id_and_hx_vals(parse_html, session):
    root = _picker(parse_html, session)

    picker_id = root.attrs["id"]
    assert picker_id
    search_input = _one(root, "pjx-roster-picker__input")
    assert (
        _one(root, "pjx-roster-picker__results").attrs["id"] == f"{picker_id}-results"
    )
    assert search_input.attrs["hx-target"] == f"#{picker_id}-results"
    assert json.loads(search_input.attrs["hx-vals"]) == {"picker_id": picker_id}


def test_one_chip_per_item_in_order_named_by_the_picker(parse_html, session):
    items = [
        PJXRosterItem(
            value="u1",
            label="Ada",
            initials="AL",
            extra="<b>admin</b>",
            detail="<i>since 2020</i>",
        ),
        PJXRosterItem(value="u2", label="Bob", src="/bob.png"),
        PJXRosterItem(value="u3", label="Cy", icon="user"),
    ]

    root = _picker(parse_html, session, items=items, remove_label="Tirar")

    chips = _one(root, "pjx-roster-picker__chips").children
    assert len(chips) == 3
    for chip, item in zip(chips, items, strict=True):
        assert "pjx-roster-picker__chip" in chip.classes
        hidden = chip.children[0]
        assert hidden.attrs["name"] == "members"
        assert hidden.attrs["value"] == item.value
        assert _one(chip, "pjx-roster-picker__chip-label").text == item.label
        button = _one(chip, "pjx-roster-picker__chip-remove")
        assert button.attrs["aria-label"] == f"Tirar: {item.label}"
    ada, bob, cy = chips
    assert _one(ada, "pjx-avatar__initials").text == "AL"
    (bold,) = _one(ada, "pjx-roster-picker__chip-extra").children
    assert bold.tag == "b"
    (italic,) = _one(ada, "pjx-roster-picker__chip-detail").children
    assert italic.tag == "i"
    (img,) = [el for el in bob.descendants() if el.tag == "img"]
    assert img.attrs["src"] == "/bob.png"
    assert _one(cy, "pjx-roster-picker__chip-icon").tag == "svg"


def test_no_items_renders_an_empty_chips_container(parse_html, session):
    root = _picker(parse_html, session)

    chips = _one(root, "pjx-roster-picker__chips")
    assert chips.children == []
    assert chips.text.strip() == ""


def test_hint_is_hidden_and_shows_limit_label(parse_html, session):
    root = _picker(parse_html, session, limit_label="Team is full")

    hint = _one(root, "pjx-roster-picker__hint")
    assert "hidden" in hint.attrs
    assert hint.text == "Team is full"


def test_max_items_is_rendered_on_the_root(parse_html, session):
    root = _picker(parse_html, session, max_items=3, items=_items("u1", "u2"))

    assert root.attrs["data-max-items"] == "3"
    assert "hidden" in _one(root, "pjx-roster-picker__hint").attrs


def test_a_picker_rendered_full_disables_the_input_and_shows_the_hint(
    parse_html, session
):
    root = _picker(
        parse_html,
        session,
        max_items=3,
        items=_items("u1", "u2", "u3"),
        limit_label="Team is full",
    )

    assert "disabled" in _one(root, "pjx-roster-picker__input").attrs
    hint = _one(root, "pjx-roster-picker__hint")
    assert "hidden" not in hint.attrs
    assert hint.text == "Team is full"


def test_a_picker_below_its_cap_keeps_the_input_enabled(parse_html, session):
    root = _picker(parse_html, session, max_items=3, items=_items("u1", "u2"))

    assert "disabled" not in _one(root, "pjx-roster-picker__input").attrs
    assert "hidden" in _one(root, "pjx-roster-picker__hint").attrs


def test_a_full_single_item_picker_is_not_capped(parse_html, session):
    root = _picker(parse_html, session, max_items=1, items=_items("u1"))

    assert "disabled" not in _one(root, "pjx-roster-picker__input").attrs
    assert "hidden" in _one(root, "pjx-roster-picker__hint").attrs


def test_a_disabled_full_picker_keeps_the_hint_hidden(parse_html, session):
    root = _picker(
        parse_html, session, max_items=2, items=_items("u1", "u2"), disabled=True
    )

    assert _by_class(root, "pjx-roster-picker__input") == []
    assert "hidden" in _one(root, "pjx-roster-picker__hint").attrs


# ── Escaping and single root ─────────────────────────────────────────────────


def test_markup_in_text_props_is_escaped_text_not_tags(parse_html, session):
    markup = "<script>alert(1)</script>"

    root = _picker(
        parse_html,
        session,
        placeholder=markup,
        limit_label=markup,
        empty_message=markup,
        remove_label=markup,
        items=[PJXRosterItem(value="u1", label=markup)],
    )

    assert [el for el in root.descendants() if el.tag == "script"] == []
    assert _one(root, "pjx-roster-picker__input").attrs["placeholder"] == markup
    assert _one(root, "pjx-roster-picker__hint").text == markup
    assert root.attrs["data-empty-message"] == markup
    assert _one(root, "pjx-roster-picker__chip-label").text == markup
    button = _one(root, "pjx-roster-picker__chip-remove")
    assert button.attrs["aria-label"] == f"{markup}: {markup}"


def test_quotes_in_attribute_props_round_trip(parse_html, session):
    root = _picker(
        parse_html,
        session,
        id="""t'e"am""",
        name='m"e&m',
        candidates_url='/people?a="1"&b=2',
        placeholder='Say "hi" & go',
        remove_label='R"x',
        empty_message='None "here" & now',
        items=_items("u1"),
    )

    assert len(root.children) == 3
    assert root.attrs["data-name"] == 'm"e&m'
    assert root.attrs["data-empty-message"] == 'None "here" & now'
    search_input = _one(root, "pjx-roster-picker__input")
    assert search_input.attrs["hx-get"] == '/people?a="1"&b=2'
    assert search_input.attrs["placeholder"] == 'Say "hi" & go'
    assert json.loads(search_input.attrs["hx-vals"]) == {"picker_id": """t'e"am"""}
    assert _one(root, "pjx-roster-picker__chip-input").attrs["name"] == 'm"e&m'
    button = _one(root, "pjx-roster-picker__chip-remove")
    assert button.attrs["aria-label"] == 'R"x: U1'


def test_text_is_escaped_exactly_once(parse_html, session):
    root = _picker(
        parse_html,
        session,
        limit_label="A & B",
        items=[PJXRosterItem(value="u1", label="C & D")],
    )

    assert _one(root, "pjx-roster-picker__hint").text == "A & B"
    assert _one(root, "pjx-roster-picker__chip-label").text == "C & D"


def test_two_pickers_in_one_session_never_share_an_id(parse_html, session):
    html = render(
        PJXRosterPicker(name="a", candidates_url="/a", items=_items("u1")), session
    ) + render(
        PJXRosterPicker(name="b", candidates_url="/b", items=_items("u1")), session
    )

    roots = parse_html(html)
    assert len(roots) == 2
    ids = [
        el.attrs["id"]
        for root in roots
        for el in [root, *root.descendants()]
        if "id" in el.attrs
    ]
    assert len(ids) == len(set(ids))


# ── Attribute pass-through ───────────────────────────────────────────────────


def test_extra_attrs_land_on_the_root_only(parse_html, session):
    root = _picker(
        parse_html,
        session,
        items=_items("u1"),
        extra_attrs={"data-team": "core", "name": "x", "form": "f", "hidden": ""},
    )

    assert root.attrs["data-team"] == "core"
    assert root.attrs["name"] == "x"
    assert root.attrs["form"] == "f"
    search_input = _one(root, "pjx-roster-picker__input")
    assert search_input.attrs["name"] == "q"
    assert search_input.attrs["form"] != "f"
    chip_input = _one(root, "pjx-roster-picker__chip-input")
    assert chip_input.attrs["name"] == "members"
    for el in root.descendants():
        assert "data-team" not in el.attrs
    assert "hidden" not in _one(root, "pjx-roster-picker__chips").attrs


def test_tag_in_a_host_template_renders_the_picker_with_inline_attributes(
    host_dir, parse_html, session
):
    host = component("RosterHost", template_dir=host_dir)

    (root,) = parse_html(render(host(id="h"), session))  # pyright: ignore[reportCallIssue]

    (picker,) = root.children
    assert "data-pjx-roster-picker" in picker.attrs
    assert picker.attrs["data-team"] == "core"
    assert picker.attrs["data-name"] == "members"
    assert _one(picker, "pjx-roster-picker__input").attrs["hx-get"] == "/people"


# ── Disabled / required / portal ─────────────────────────────────────────────


def test_disabled_drops_the_search_wrapper_and_remove_buttons_but_keeps_hidden_inputs(
    parse_html, session
):
    root = _picker(parse_html, session, disabled=True, items=_items("u1", "u2"))

    assert "data-disabled" in root.attrs
    assert _by_class(root, "pjx-roster-picker__search") == []
    assert _by_class(root, "pjx-roster-picker__input") == []
    assert _by_class(root, "pjx-roster-picker__results") == []
    assert [el for el in root.descendants() if el.tag == "button"] == []
    hidden = _by_class(root, "pjx-roster-picker__chip-input")
    assert [el.attrs["value"] for el in hidden] == ["u1", "u2"]
    for el in hidden:
        assert el.attrs["name"] == "members"
        assert "disabled" not in el.attrs
    chips, hint = root.children
    assert "pjx-roster-picker__chips" in chips.classes
    assert "pjx-roster-picker__hint" in hint.classes


def test_required_adds_a_visually_hidden_validity_input_after_the_hint(
    parse_html, session
):
    root = _picker(parse_html, session, required=True, items=_items("u1", "u2"))

    assert len(root.children) == 4
    validity = root.children[-1]
    assert validity.tag == "input"
    assert "pjx-roster-picker__validity" in validity.classes
    assert validity.attrs["type"] == "text"
    assert "required" in validity.attrs
    assert validity.attrs["tabindex"] == "-1"
    assert validity.attrs["aria-hidden"] == "true"
    assert "name" not in validity.attrs
    assert "disabled" not in validity.attrs
    assert validity.attrs["value"] == "u1,u2"
    assert _one(root, "pjx-roster-picker__input").attrs["aria-required"] == "true"


def test_required_with_no_items_gives_an_empty_validity_value(parse_html, session):
    root = _picker(parse_html, session, required=True)

    assert _one(root, "pjx-roster-picker__validity").attrs["value"] == ""


def test_required_and_disabled_validity_input_is_disabled(parse_html, session):
    root = _picker(parse_html, session, required=True, disabled=True)

    assert "disabled" in _one(root, "pjx-roster-picker__validity").attrs


def test_not_required_renders_no_validity_input(parse_html, session):
    root = _picker(parse_html, session, items=_items("u1"))

    assert _by_class(root, "pjx-roster-picker__validity") == []


def test_portal_adds_the_portal_flag(parse_html, session):
    root = _picker(parse_html, session, portal=True)

    assert "data-pjx-roster-picker-portal" in root.attrs


# ── Assets ───────────────────────────────────────────────────────────────────


def test_render_records_the_picker_css_and_js_assets(session):
    # A bare RenderSession does not collect assets until accumulate_assets is
    # subscribed, the same wiring the other builtin asset tests use.
    session.on_rendered.append(accumulate_assets)

    render(PJXRosterPicker(name="members", candidates_url="/people"), session)

    assert CSS_PATH in {path.resolve() for path in session.css_assets}
    assert JS_PATH in {path.resolve() for path in session.js_assets}


def test_package_ships_css_next_to_the_component():
    assert (PACKAGE_DIR / "pjx_roster_picker.py").is_file()
    assert CSS_PATH.is_file()


# ── CSS ──────────────────────────────────────────────────────────────────────


def test_css_declares_tokens_in_a_where_root_block_defaulting_to_semantic_tokens():
    tokens = _token_block()

    for token, default in SEMANTIC_TOKENS.items():
        assert tokens[token].startswith(default), token
    for token in LITERAL_TOKENS:
        assert token in tokens, token
    assert tokens["--pjx-roster-picker-room"] == "var(--pjx-roster-picker-max-h)"
    used = set(re.findall(r"var\((--pjx-roster-picker-[\w-]+)", _css()))
    assert used <= set(tokens)


def test_css_styles_every_block_class():
    selectors = " ".join(selector for selector, _ in _rules())

    for name in CSS_CLASSES:
        assert re.search(re.escape("." + name) + r"(?![\w-])", selectors), name


def test_css_results_height_is_capped_by_the_room_token():
    (body,) = [
        body for selector, body in _rules() if selector == ".pjx-roster-picker__results"
    ]

    assert "position: absolute" in body
    assert "overflow-y: auto" in body
    assert (
        "max-height: min(var(--pjx-roster-picker-max-h), var(--pjx-roster-picker-room))"
        in body
    )


def test_css_validity_input_is_clipped_not_display_none():
    validity_rules = [
        body for selector, body in _rules() if "pjx-roster-picker__validity" in selector
    ]

    assert validity_rules
    body = " ".join(validity_rules)
    assert "position: absolute" in body
    assert "width: 1px" in body
    assert "height: 1px" in body
    assert "clip-path: inset(50%)" in body
    assert "overflow: hidden" in body
    assert "display: none" not in body


def test_css_hides_a_picked_row_despite_its_flex_display():
    (body,) = [
        body
        for selector, body in _rules()
        if selector == ".pjx-roster-picker__pick[hidden]"
    ]

    assert "display: none" in body


def test_css_selectors_stay_inside_the_block():
    for selector, _ in _rules():
        for part in selector.split(","):
            assert part.strip().startswith(".pjx-roster-picker"), part


def test_css_has_a_reduced_motion_query():
    css = _css()

    assert "@media (prefers-reduced-motion: reduce)" in css
    reduced = css.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    clamped = {
        part.strip()
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", reduced)
        if "transition: none" in body
        for part in selector.split(",")
    }
    for selector, body in _rules():
        if "transition:" in body and "transition: none" not in body:
            for part in selector.split(","):
                assert part.strip() in clamped, part


def test_exported_from_the_builtins_namespace():
    from pyjinhx import builtins

    assert "PJXRosterPicker" in builtins.__all__
    assert builtins.PJXRosterPicker is PJXRosterPicker
