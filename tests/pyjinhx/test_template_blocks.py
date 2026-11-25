"""Inline ``{#css#}``/``{#js#}`` blocks: scanning, the asset they become, and
how that asset rides the existing pipeline."""

import pickle
from pathlib import Path

import pytest
from jinja2 import Environment, TemplateSyntaxError

from pyjinhx.template_blocks import InlineAsset, find_block


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
    source = "{#css .a {} #}\n<div></div>\n{#css .b {} #}\n"

    with pytest.raises(TemplateSyntaxError) as raised:
        find_block(source, "css", "/app/card.pjx")

    assert raised.value.lineno == 3
    assert raised.value.filename == "/app/card.pjx"
    assert "line 1" in raised.value.message  # type: ignore[operator]


def test_blocks_are_plain_jinja_comments_and_never_render():
    source = "{#def title: str #}\n{#css .a { color: red; } #}\n<p>{{ title }}</p>\n{#js run(); #}"

    rendered = Environment().from_string(source).render(title="hi")

    assert rendered.strip() == "<p>hi</p>"


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def test_an_inline_asset_reads_as_its_block_body(tmp_path):
    template = _write(tmp_path / "card.pjx", "{#css .card {} #}<div></div>")

    asset = InlineAsset(template, "css")

    assert asset.read_text() == ".card {}"
    assert asset.read_bytes() == b".card {}"


def test_an_inline_asset_is_named_after_its_template_and_kind(tmp_path):
    asset = InlineAsset(tmp_path / "card.pjx", "js")

    assert str(asset) == f"{tmp_path}/card.pjx#js"
    assert asset.template == tmp_path / "card.pjx"
    assert asset.kind == "js"


def test_an_inline_asset_rereads_its_template_so_edits_show_up(tmp_path):
    template = _write(tmp_path / "card.pjx", "{#css .old {} #}<div></div>")
    asset = InlineAsset(template, "css")
    _write(template, "{#css .new {} #}<div></div>")

    assert asset.read_text() == ".new {}"


def test_an_inline_asset_whose_block_was_removed_reads_empty(tmp_path):
    template = _write(tmp_path / "card.pjx", "{#css .old {} #}<div></div>")
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
    template = _write(tmp_path / "card.pjx", "{#css .card {} #}<div></div>")

    restored = pickle.loads(pickle.dumps(InlineAsset(template, "css")))

    assert isinstance(restored, InlineAsset)
    assert restored.read_text() == ".card {}"
