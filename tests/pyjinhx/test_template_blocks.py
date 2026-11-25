"""Inline ``{#css#}``/``{#js#}`` blocks: scanning, the asset they become, and
how that asset rides the existing pipeline."""

import pickle
from pathlib import Path

import pytest
from jinja2 import Environment, TemplateSyntaxError

from pyjinhx import discovery
from pyjinhx.assets import (
    AssetMode,
    all_assets,
    asset_manifest,
    asset_token,
    emit_assets,
)
from pyjinhx.classless import component
from pyjinhx.reactive.assets import missing_asset_oob
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession, accumulate_assets
from pyjinhx.template_blocks import InlineAsset, find_block, inline_assets


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
    _write(tmp_path / "card.pjx", "<div></div>\n{#js a(); #}\n{#js b(); #}\n")

    with pytest.raises(TemplateSyntaxError) as raised:
        component("Card", template_dir=tmp_path)

    assert raised.value.lineno == 3
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
        inline_assets(path)

    assert raised.value.lineno == 4
    assert raised.value.filename == str(path)
    message = raised.value.message or ""
    assert '"#" + "}"' in message
    assert "sibling" in message


def test_a_literal_comment_close_in_a_document_without_blocks_is_left_alone(tmp_path):
    path = _write(tmp_path / "card.pjx", "<div>#} not a comment</div>\n")

    assert inline_assets(path) == (None, None)
