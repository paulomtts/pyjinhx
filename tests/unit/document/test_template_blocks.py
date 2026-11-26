"""Inline ``{#css#}``/``{#js#}`` blocks: scanning, the asset they become, and
how that asset rides the existing pipeline."""

import json
import pickle
from pathlib import Path

import pytest
from jinja2 import Environment, TemplateSyntaxError

from pyjinhx import manifest
from pyjinhx.components import discovery
from pyjinhx.components.classless import component
from pyjinhx.document import scanner
from pyjinhx.document.template_blocks import (
    BlockTemplateSyntaxError,
    InlineAsset,
    find_block,
    find_header,
    hide_block_lines,
    inline_assets,
)
from pyjinhx.reactive.assets import missing_asset_oob
from pyjinhx.rendering.assets import (
    AssetMode,
    all_assets,
    asset_manifest,
    asset_token,
    emit_assets,
)
from pyjinhx.rendering.pipeline import render
from pyjinhx.rendering.session import (
    AbsolutePathLoader,
    RenderSession,
    accumulate_assets,
)


def test_a_template_without_the_block_has_none():
    assert find_block("<div></div>", "css", "card.pjx") is None


def test_the_block_body_is_returned_without_the_keyword_or_padding():
    source = "{#css\n.card { color: red; }\n#}\n<div></div>"

    block = find_block(source, "css", "card.pjx")

    assert block is not None
    assert block.body == ".card { color: red; }"
    assert block.line == 1


def test_the_line_counts_from_one_at_the_block_opening():
    source = "{#def title: str #}\n<div></div>\n\n{#js\nrun();\n#}\n"

    block = find_block(source, "js", "card.pjx")

    assert block is not None
    assert block.line == 4


def test_a_prose_comment_that_starts_with_the_word_is_not_a_block():
    """The keyword has to touch ``{#`` — a spaced comment stays a comment."""
    assert find_block("{# css tweaks for safari #}<div></div>", "css", "x") is None


def test_a_one_line_comment_after_the_keyword_is_prose_not_a_block():
    """A block's body starts on the line after its keyword."""
    source = "{#js hack: remove later #}\n<div></div>\n{#js and this too #}\n"

    assert find_block(source, "js", "x") is None
    assert find_block("{#css .a {} #}<div></div>", "css", "x") is None


def test_a_block_may_have_trailing_spaces_after_its_keyword():
    block = find_block("{#css  \n.a {}\n#}", "css", "x")

    assert block is not None
    assert block.body == ".a {}"


def test_a_longer_keyword_is_not_mistaken_for_a_shorter_one():
    assert find_block("{#cssx a #}<div></div>", "css", "x") is None
    assert find_block("{#json {} #}<div></div>", "js", "x") is None


def test_an_empty_block_counts_as_no_block():
    assert find_block("{#css #}<div></div>", "css", "x") is None
    assert find_block("{#css#}<div></div>", "css", "x") is None


def test_jinja_syntax_inside_the_body_is_kept_verbatim():
    source = "{#js\nconst o = {{a: 1}}; if (x) {% raw %}\n#}<div></div>"

    block = find_block(source, "js", "x")

    assert block is not None
    assert block.body == "const o = {{a: 1}}; if (x) {% raw %}"


def test_a_second_block_of_the_same_kind_raises_at_its_line():
    source = "{#css\n.a {}\n#}\n<div></div>\n{#css\n.b {}\n#}\n"

    with pytest.raises(TemplateSyntaxError) as raised:
        find_block(source, "css", "/app/card.pjx")

    assert raised.value.lineno == 5
    assert raised.value.filename == "/app/card.pjx"
    assert "line 1" in raised.value.message  # type: ignore[operator]


def test_blocks_are_plain_jinja_comments_and_never_render():
    source = "{#def title: str #}\n{#css\n.a { color: red; }\n#}\n<p>{{ title }}</p>\n{#js\nrun();\n#}"

    rendered = Environment().from_string(source).render(title="hi")

    assert rendered.strip() == "<p>hi</p>"


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def test_an_inline_asset_reads_as_its_block_body(tmp_path):
    template = _write(tmp_path / "card.pjx", "{#css\n.card {}\n#}<div></div>")

    asset = InlineAsset(template, "css")

    assert asset.read_text() == ".card {}"
    assert asset.read_bytes() == b".card {}"


def test_an_inline_asset_is_named_after_its_template_and_kind(tmp_path):
    asset = InlineAsset(tmp_path / "card.pjx", "js")

    assert str(asset) == f"{tmp_path}/card.pjx#js"
    assert asset.template == tmp_path / "card.pjx"
    assert asset.kind == "js"


def test_an_inline_asset_rereads_its_template_so_edits_show_up(tmp_path):
    template = _write(tmp_path / "card.pjx", "{#css\n.old {}\n#}<div></div>")
    asset = InlineAsset(template, "css")
    _write(template, "{#css\n.new {}\n#}<div></div>")

    assert asset.read_text() == ".new {}"


def test_an_inline_asset_whose_block_was_removed_reads_empty(tmp_path):
    template = _write(tmp_path / "card.pjx", "{#css\n.old {}\n#}<div></div>")
    asset = InlineAsset(template, "css")
    _write(template, "<div></div>")

    assert asset.read_text() == ""


def test_an_inline_asset_sorts_after_the_sibling_file_of_its_kind(tmp_path):
    sibling_css = tmp_path / "card.css"
    sibling_js = tmp_path / "card.js"
    inline_css = InlineAsset(tmp_path / "card.pjx", "css")
    inline_js = InlineAsset(tmp_path / "card.pjx", "js")

    assert sorted([inline_css, sibling_css], key=str) == [sibling_css, inline_css]
    assert sorted([inline_js, sibling_js], key=str) == [sibling_js, inline_js]


def test_derived_paths_are_plain_paths(tmp_path):
    asset = InlineAsset(tmp_path / "card.pjx", "css")

    assert type(asset.parent) is not InlineAsset
    assert asset.parent == tmp_path
    assert type(asset.resolve()) is not InlineAsset


def test_an_inline_asset_survives_pickling(tmp_path):
    """The tier-2 disk cache pickles rendered levels, descriptor and all."""
    template = _write(tmp_path / "card.pjx", "{#css\n.card {}\n#}<div></div>")

    restored = pickle.loads(pickle.dumps(InlineAsset(template, "css")))

    assert isinstance(restored, InlineAsset)
    assert restored.read_text() == ".card {}"


# --- the descriptor and the asset pipeline ---------------------------------


@pytest.fixture
def reset_registry():
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    yield
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def _collecting_session() -> RenderSession:
    """A session that collects assets the way a wired app's does."""
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    return session


CARD = """{#def title: str #}
<div class="card">{{ title }}</div>
{#css
.card { color: red; }
#}
{#js
console.log("card");
#}
"""


def test_the_descriptor_lists_the_inline_blocks(tmp_path, reset_registry):
    template = _write(tmp_path / "card.pjx", CARD)

    descriptor = component("Card", template_dir=tmp_path).__pjx_descriptor__

    assert descriptor.css_paths == (InlineAsset(template, "css"),)
    assert descriptor.js_paths == (InlineAsset(template, "js"),)


def test_a_sibling_file_and_a_block_are_both_listed_sibling_first(
    tmp_path, reset_registry
):
    template = _write(tmp_path / "card.pjx", CARD)
    _write(tmp_path / "card.css", ".sibling {}")

    descriptor = component("Card", template_dir=tmp_path).__pjx_descriptor__

    assert descriptor.css_paths == (tmp_path / "card.css", InlineAsset(template, "css"))


def test_a_duplicate_block_fails_registration_at_its_line(tmp_path, reset_registry):
    _write(tmp_path / "card.pjx", "<div></div>\n{#js\na();\n#}\n{#js\nb();\n#}\n")

    with pytest.raises(TemplateSyntaxError) as raised:
        component("Card", template_dir=tmp_path)

    assert raised.value.lineno == 5
    assert raised.value.filename == str(tmp_path / "card.pjx")


def test_rendering_inlines_the_blocks_and_strips_them_from_markup(
    tmp_path, reset_registry
):
    template = _write(tmp_path / "card.pjx", CARD)
    cls = component("Card", template_dir=tmp_path)

    out = render(cls(title="hi"), _collecting_session())  # pyright: ignore[reportCallIssue]

    token = asset_token(InlineAsset(template, "css"))
    assert f'<style data-pjx-asset="{token}">.card {{ color: red; }}</style>' in out
    assert '<script>console.log("card");</script>' in out
    assert out.count(".card { color: red; }") == 1
    assert "{#" not in out


def test_two_instances_ship_the_block_once(tmp_path, reset_registry):
    _write(tmp_path / "card.pjx", CARD)
    _write(tmp_path / "page.pjx", "<main><Card title='a'/><Card title='b'/></main>")
    component("Card", template_dir=tmp_path)
    page = component("Page", template_dir=tmp_path)

    out = render(page(), _collecting_session())

    assert out.count(".card { color: red; }") == 1
    assert out.count('console.log("card")') == 1


def test_sibling_and_block_render_sibling_first(tmp_path, reset_registry):
    _write(tmp_path / "card.pjx", CARD)
    _write(tmp_path / "card.css", ".sibling {}")
    cls = component("Card", template_dir=tmp_path)

    out = render(cls(title="hi"), _collecting_session())  # pyright: ignore[reportCallIssue]

    assert out.index(".sibling {}") < out.index(".card { color: red; }")


def test_none_mode_ships_no_block(tmp_path, reset_registry):
    _write(tmp_path / "card.pjx", CARD)
    cls = component("Card", template_dir=tmp_path)
    session = _collecting_session()
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.NONE

    out = render(cls(title="hi"), session)  # pyright: ignore[reportCallIssue]

    assert "color: red" not in out
    assert "console.log" not in out


def test_link_mode_refuses_a_block_and_names_its_template(tmp_path, reset_registry):
    template = _write(tmp_path / "card.pjx", CARD)
    session = RenderSession()
    session.css_mode = AssetMode.LINK
    session.css_assets.add(InlineAsset(template, "css"))

    with pytest.raises(ValueError, match="card.pjx"):
        emit_assets(session, resolver=lambda path: f"/static/{path.name}")
    with pytest.raises(ValueError, match="card.pjx"):
        asset_manifest(session, resolver=lambda path: f"/static/{path.name}")


def test_all_assets_lists_the_blocks_for_a_bundle(tmp_path, reset_registry):
    template = _write(tmp_path / "card.pjx", CARD)
    component("Card", template_dir=tmp_path)

    css, js = all_assets()

    assert InlineAsset(template, "css") in css
    assert InlineAsset(template, "js") in js


def test_the_swap_in_delta_ships_a_block_the_client_lacks(tmp_path):
    template = _write(tmp_path / "card.pjx", CARD)
    css = InlineAsset(template, "css")
    js = InlineAsset(template, "js")
    session = RenderSession()
    session.css_assets.add(css)
    session.js_assets.add(js)

    fragment = missing_asset_oob([], frozenset({asset_token(js)}), session)

    assert (
        f'<style data-pjx-asset="{asset_token(css)}" '
        'hx-swap-oob="beforeend:head">.card { color: red; }</style>'
    ) in fragment
    assert "console.log" not in fragment


def test_a_subclass_without_a_template_ships_its_parents_blocks(
    tmp_path, reset_registry
):
    template = _write(tmp_path / "card.pjx", CARD)
    card = component("Card", template_dir=tmp_path)

    class FancyCard(card):
        pass

    assert FancyCard.__pjx_descriptor__.css_paths == (InlineAsset(template, "css"),)


def test_a_stray_comment_close_in_a_js_body_raises_at_its_line(tmp_path):
    path = _write(tmp_path / "card.pjx", '<div></div>\n{#js\nlet s = "#}";\n#}\n')

    with pytest.raises(TemplateSyntaxError) as raised:
        inline_assets(path, path.read_text())

    assert raised.value.lineno == 4
    assert raised.value.filename == str(path)
    message = raised.value.message or ""
    assert '"#" + "}"' in message
    assert "sibling" in message


def test_a_literal_comment_close_in_a_document_without_blocks_is_left_alone(tmp_path):
    path = _write(tmp_path / "card.pjx", "<div>#} not a comment</div>\n")

    assert inline_assets(path, path.read_text()) == (None, None)


# --- a block on its own line leaves no blank line ---------------------------


def _render_file(path: Path, **context: object) -> str:
    return (
        Environment(loader=AbsolutePathLoader())
        .get_template(str(path))
        .render(**context)
    )


@pytest.mark.parametrize(
    ("source", "rendered"),
    [
        ("{#def title: str #}\n<p>{{ title }}</p>\n", "<p>hi</p>"),
        ("<p>{{ title }}</p>\n{#css\n.p {}\n#}\n", "<p>hi</p>"),
        ("<p>{{ title }}</p>\n{#css\n.p {}\n#}", "<p>hi</p>"),
        ("<p>a</p>\n  {#js\nrun();\n#}  \n<p>{{ title }}</p>", "<p>a</p>\n<p>hi</p>"),
        (
            "{#def title: str #}\n{#css\n.p {}\n#}\n<p>{{ title }}</p>\n{#js\nrun();\n#}\n",
            "<p>hi</p>",
        ),
    ],
    ids=["header", "trailing-block", "last-line", "between-lines", "all-three"],
)
def test_a_block_on_its_own_line_takes_the_line_with_it(tmp_path, source, rendered):
    """So a header, or an asset folded in from a sibling file, never changes
    the markup a template renders."""
    path = _write(tmp_path / "note.pjx", source)

    assert _render_file(path, title="hi") == rendered


@pytest.mark.parametrize(
    "source",
    [
        "<p>{{ title }}</p>{#css\n.p {}\n#}\n<i></i>",
        "<p>{{ title }}</p>\n{#css\n.p {}\n#}<i></i>",
    ],
    ids=["after-markup", "before-markup"],
)
def test_a_block_sharing_a_line_with_markup_keeps_the_line(tmp_path, source):
    path = _write(tmp_path / "note.pjx", source)

    assert _render_file(path, title="hi") == "<p>hi</p>\n<i></i>"


def test_a_prose_comment_on_its_own_line_keeps_its_line(tmp_path):
    path = _write(tmp_path / "note.pjx", "<p>a</p>\n{# a note #}\n<p>b</p>")

    assert _render_file(path) == "<p>a</p>\n\n<p>b</p>"


def test_hidden_block_lines_keep_every_line_number(tmp_path):
    path = _write(
        tmp_path / "note.pjx",
        "{#def title: str #}\n{#css\n.p {}\n#}\n<p>\n{% if %}\n</p>\n{#js\nrun();\n#}\n",
    )

    with pytest.raises(TemplateSyntaxError) as raised:
        _render_file(path)

    assert raised.value.lineno == 6


def test_an_inline_asset_reports_its_kind_as_the_suffix(tmp_path):
    asset = InlineAsset(tmp_path / "card.pjx", "css")

    assert asset.suffix == ".css"
    assert asset.suffixes == [".css"]
    assert asset.stem == "card"
    assert asset.name == "card.css"
    assert str(asset) == f"{tmp_path}/card.pjx#css"


def test_a_class_inline_asset_is_named_after_its_module(tmp_path):
    asset = InlineAsset(tmp_path / "widgets.py", "js", inline_class="Card")

    assert asset.suffix == ".js"
    assert asset.stem == "widgets"
    assert asset.name == "widgets.js"


def test_a_python_block_alone_on_its_lines_renders_as_nothing():
    source = "{#python\nx = 1\n#}\n<p>hi</p>"

    assert Environment().from_string(hide_block_lines(source)).render() == "<p>hi</p>"


def test_markup_after_a_python_block_keeps_its_line_numbers():
    source = "{#python\nx = 1\n#}\n<p>{% if %}</p>"

    with pytest.raises(TemplateSyntaxError) as raised:
        Environment().from_string(hide_block_lines(source))

    assert raised.value.lineno == 4


def test_a_python_block_cut_short_by_a_closer_line_leaves_a_stray_closer():
    source = "{#python\nx = 1\n#}\ny = 2\n#}\n<p></p>"

    with pytest.raises(TemplateSyntaxError, match="stray") as raised:
        inline_assets(Path("card.pjx"), source)

    assert raised.value.lineno == 5


def test_css_text_inside_a_python_body_is_not_a_css_block():
    source = '{#python\nx = "{#css"\n#}\n<p></p>\n{#css\n.a { color: red; }\n#}\n'

    block = find_block(source, "css", "card.pjx")

    assert block is not None
    assert block.line == 5
    assert block.body == ".a { color: red; }"


@pytest.mark.parametrize("keyword", ["python", "css"])
def test_a_block_with_crlf_endings_renders_as_nothing(keyword):
    source = f"{{#{keyword}\r\nx = 1\r\n#}}\r\n<p>hi</p>"

    assert Environment().from_string(hide_block_lines(source)).render() == "<p>hi</p>"


def test_a_block_inside_a_raw_region_is_not_a_block():
    source = "{% raw %}\n{#css\n.a { color: red; }\n#}\n{% endraw %}\n"

    assert find_block(source, "css", "card.pjx") is None


def test_a_comment_closer_inside_a_tag_string_is_not_stray():
    source = '{#css\n.a { color: red; }\n#}\n<p>{{ "#}" }}</p>\n{% raw %}#}{% endraw %}'

    inline_assets(Path("card.pjx"), source)


def test_a_comment_opener_inside_a_tag_string_does_not_start_a_block():
    source = '{% set h = "{#css" %}\n<p>{{ h }}</p>\n{#css\n.a { color: red; }\n#}\n'

    block = find_block(source, "css", "card.pjx")

    assert block is not None
    assert block.line == 3


def test_every_block_error_carries_a_code():
    with pytest.raises(BlockTemplateSyntaxError) as second:
        find_block("{#css\na\n#}\n{#css\nb\n#}", "css", "card.pjx")
    with pytest.raises(BlockTemplateSyntaxError) as stray:
        inline_assets(Path("card.pjx"), "{#css\na\n#}\n#}")

    assert second.value.code == "second-block"
    assert stray.value.code == "stray-comment-close"


def test_the_error_on_the_lowest_line_is_the_one_raised():
    source = "{#python\nx = '#}'\n#}\n{#css\na\n#}\n{#css\nb\n#}\n"

    with pytest.raises(SyntaxError) as raised:
        inline_assets(Path("card.pjx"), source)

    assert raised.value.lineno == 2


def test_find_header_gives_the_signature_where_it_starts_and_the_opener_line():
    source = "<p></p>\n{#def\n  a: int = 1 #}\n<b></b>"
    header = find_header(source, "x")
    assert header is not None
    assert header.signature == "a: int = 1"
    assert source[header.offset :].startswith("a: int = 1")
    assert header.line == 2


def test_find_header_reads_the_legacy_spaced_header_first_in_the_document():
    header = find_header("{# def a: int #}\n<b></b>", "x")
    assert header is not None
    assert (header.signature, header.offset, header.line) == ("a: int", 7, 1)
    assert find_header("<b></b>\n{# def a: int #}", "x") is None


def test_find_header_is_none_without_a_header():
    assert find_header("<b>{# def #}</b>", "x") is None


def test_find_header_offset_skips_the_keyword_even_when_the_signature_is_in_it():
    source = "{#def e#}<b></b>"
    header = find_header(source, "x")
    assert header is not None
    assert source[header.offset :].startswith("e#}")


# The block grammar corpus: every case under tests/fixtures/block_grammar,
# scanned with the real scanners, must give the recorded blocks or error.


CORPUS = Path(__file__).resolve().parents[2] / "fixtures" / "block_grammar"


def _scan(source: str, filename: str) -> tuple[list[dict], dict | None]:
    """The blocks and the lowest-line error the scanners report for ``source``."""
    blocks: list[tuple[str, int, int]] = []
    errors: list[BlockTemplateSyntaxError | scanner.BlockSyntaxError] = []
    for keyword in ("def", "css", "js"):
        try:
            block = find_block(source, keyword, filename)
        except BlockTemplateSyntaxError as error:
            errors.append(error)
        else:
            if block is not None:
                blocks.append((keyword, block.line, block.close_line))
    try:
        python = scanner.python_block(source, filename)
    except scanner.BlockSyntaxError as error:
        errors.append(error)
    else:
        if python is not None:
            blocks.append(("python", python.open_line, python.close_line))
    try:
        inline_assets(Path(filename), source)
    except (BlockTemplateSyntaxError, scanner.BlockSyntaxError) as error:
        errors.append(error)
    if errors:
        first = min(errors, key=lambda error: error.lineno or 0)
        return [], {"code": first.code, "line": first.lineno}
    return [_recorded(*block) for block in sorted(blocks, key=lambda b: b[1])], None


def _recorded(keyword: str, opened: int, closed: int) -> dict:
    """A block as the corpus writes it down."""
    block: dict = {"keyword": keyword, "open_line": opened}
    if keyword != "def":
        block["body_lines"] = [opened + 1, closed - 1] if closed - opened > 1 else None
    block["close_line"] = closed
    return block


@pytest.mark.parametrize("case", sorted(CORPUS.glob("*.pjx")), ids=lambda p: p.stem)
def test_the_scanners_agree_with_the_recorded_case(case, request):
    expected = json.loads(case.with_suffix(".json").read_text(encoding="utf-8"))
    source = case.read_bytes().decode("utf-8-sig")

    if "known_gap" in expected:
        # Jinja's own answer is recorded; pyjinhx differs, and this fails
        # loudly once it stops.
        request.applymarker(pytest.mark.xfail(strict=True, reason="known_gap"))

    blocks, error = _scan(source, case.name)

    assert (blocks, error) == (expected["blocks"], expected["error"])


def test_the_corpus_has_a_case_for_every_error_code():
    recorded = (
        json.loads(path.read_text(encoding="utf-8")) for path in CORPUS.glob("*.json")
    )

    assert {case["error"]["code"] for case in recorded if case["error"]} == {
        scanner.PYTHON_BLOCK_EARLY_CLOSE,
        scanner.SECOND_BLOCK,
        scanner.CLOSER_NOT_AT_LINE_START,
        scanner.UNCLOSED_BLOCK,
        scanner.TEXT_AFTER_CLOSER,
        scanner.STRAY_COMMENT_CLOSE,
    }


@pytest.mark.parametrize("case", sorted(CORPUS.glob("*.pjx")), ids=lambda p: p.stem)
def test_the_manifest_scan_agrees_with_the_recorded_case(case, request):
    expected = json.loads(case.with_suffix(".json").read_text(encoding="utf-8"))
    source = case.read_bytes().decode("utf-8-sig")

    if "known_gap" in expected:
        request.applymarker(pytest.mark.xfail(strict=True, reason="known_gap"))

    blocks, errors = manifest.scan_blocks(source, case.name)

    if expected["error"]:
        assert (errors[0]["code"], errors[0]["range"]["start"]["line"]) == (
            expected["error"]["code"],
            expected["error"]["line"],
        )
    else:
        assert errors == []
        assert blocks == expected["blocks"]
