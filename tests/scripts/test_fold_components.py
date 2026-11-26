"""Tests for fold_components: assets and template folds, including inline templates.

Every fold is proved the way a user would trust it: render the component from
the files before, fold, render again from the files after, and compare.
"""

import ast
import textwrap

import pytest

from tests.scripts._fold_helpers import (
    CARD_CSS,
    CARD_PJX,
    CARD_PY,
    make_card,
    render_class,
    run,
    write,
)

# --- assets inside an inline template ----------------------------------------


CHIP_PY = '''
    from pyjinhx import BaseComponent


    class Chip(BaseComponent):
        label: str

        template = r"""
        <i class="chip">{{ label }}</i>
        """
'''


# --- assets -----------------------------------------------------------------


def test_assets_folds_a_sibling_css_into_a_block_and_deletes_it(
    tmp_path, monkeypatch, capsys
):
    module = make_card(tmp_path)
    css = write(tmp_path / "card.css", CARD_CSS)
    before = render_class(module, "Card", monkeypatch, title="hi")

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert not css.exists()
    assert "{#css\n.card { color: red; }\n#}" in (tmp_path / "card.pjx").read_text()
    assert render_class(module, "Card", monkeypatch, title="hi") == before
    assert ".card { color: red; }" in before
    assert "1 folded" in out


def test_assets_folds_a_sibling_js_beside_an_existing_css_block(
    tmp_path, monkeypatch, capsys
):
    module = make_card(tmp_path, CARD_PJX + "{#css\n.card { top: 0; }\n#}\n")
    write(tmp_path / "card.js", "console.log('card');\n")
    before = render_class(module, "Card", monkeypatch, title="hi")

    code, _ = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert not (tmp_path / "card.js").exists()
    assert render_class(module, "Card", monkeypatch, title="hi") == before


def test_assets_dry_run_prints_a_diff_and_writes_nothing(tmp_path, capsys):
    make_card(tmp_path)
    css = write(tmp_path / "card.css", CARD_CSS)

    code, out = run("assets", tmp_path, capsys=capsys)

    assert code == 0
    assert css.exists()
    assert (tmp_path / "card.pjx").read_text() == CARD_PJX
    assert "+{#css" in out
    assert "dry run" in out


def test_assets_is_idempotent(tmp_path, capsys):
    make_card(tmp_path)
    write(tmp_path / "card.css", CARD_CSS)
    run("assets", tmp_path, "--write", capsys=capsys)
    folded = (tmp_path / "card.pjx").read_text()

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert (tmp_path / "card.pjx").read_text() == folded
    assert "0 folded" in out


def test_assets_refuses_a_body_holding_a_comment_terminator(tmp_path, capsys):
    make_card(tmp_path)
    css = write(tmp_path / "card.css", "a::after { content: '#}'; }\n")

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "#}" in out and "card.css" in out


def test_assets_refuses_when_the_template_already_has_that_block(tmp_path, capsys):
    make_card(tmp_path, CARD_PJX + "{#css\n.x {}\n#}\n")
    css = write(tmp_path / "card.css", CARD_CSS)

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "already" in out


def test_assets_refuses_an_asset_a_subclass_with_its_own_template_inherits(
    tmp_path, capsys
):
    make_card(tmp_path)
    write(
        tmp_path / "fancy_card.py",
        """
        from card import Card


        class FancyCard(Card):
            pass
        """,
    )
    write(tmp_path / "fancy_card.pjx", "<section>{{ title }}</section>\n")
    css = write(tmp_path / "card.css", CARD_CSS)

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "FancyCard" in out


def test_assets_refuses_when_an_inheriting_subclass_has_its_own_sibling_file(
    tmp_path, capsys
):
    """Its own .css shadows the parent's file but would not shadow a block."""
    make_card(tmp_path)
    write(
        tmp_path / "fancy_card.py",
        """
        from card import Card


        class FancyCard(Card):
            pass
        """,
    )
    write(tmp_path / "fancy_card.css", ".fancy {}\n")
    css = write(tmp_path / "card.css", CARD_CSS)

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "FancyCard" in out and "fancy_card.css" in out


def test_assets_reports_every_line_under_the_root_that_names_the_file(tmp_path, capsys):
    components = tmp_path / "components"
    make_card(components)
    write(components / "card.css", CARD_CSS)
    write(tmp_path / "views.py", "BORROWED = HERE / 'card.css'\n")
    write(tmp_path / "tests" / "test_card.py", "x = 1\nread('card.css')\n")
    write(tmp_path / "other.py", "print('card.js')\n")

    code, out = run("assets", components, "--root", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert "views.py:1:" in out and "test_card.py:2:" in out
    assert "other.py" not in out
    assert "2 references" in out
    assert not (components / "card.css").exists()


def test_assets_still_processes_the_rest_after_a_refusal(tmp_path, capsys):
    make_card(tmp_path)
    write(tmp_path / "card.css", "a { content: '#}'; }\n")
    write(tmp_path / "chip.pjx", "<i></i>\n")
    write(tmp_path / "chip.js", "go();\n")

    code, _ = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert not (tmp_path / "chip.js").exists()
    assert "{#js\ngo();\n#}" in (tmp_path / "chip.pjx").read_text()


# --- template ---------------------------------------------------------------


def test_template_folds_the_pjx_into_the_class_as_its_last_statement(
    tmp_path, monkeypatch, capsys
):
    module = make_card(tmp_path)
    before = render_class(module, "Card", monkeypatch, title="hi")

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    folded = module.read_text()
    assert code == 0
    assert not (tmp_path / "card.pjx").exists()
    assert folded.endswith(
        '    title: str\n\n    template = r"""\n'
        '    <div class="card">{{ title }}</div>\n    """\n'
    )
    ast.parse(folded)
    assert render_class(module, "Card", monkeypatch, title="hi") == before
    assert "1 folded" in out


def test_template_keeps_nested_markup_indentation(tmp_path, monkeypatch, capsys):
    module = make_card(
        tmp_path, '<div class="card">\n  <h1>{{ title }}</h1>\n\n  <p>x</p>\n</div>\n'
    )
    before = render_class(module, "Card", monkeypatch, title="hi")

    run("template", tmp_path, "--write", capsys=capsys)

    assert render_class(module, "Card", monkeypatch, title="hi") == before


def test_template_replaces_a_pass_body(tmp_path, monkeypatch, capsys):
    module = write(
        tmp_path / "badge.py",
        """
        from pyjinhx import BaseComponent


        class Badge(BaseComponent):
            pass
        """,
    )
    write(tmp_path / "badge.pjx", "<b>badge</b>\n")
    before = render_class(module, "Badge", monkeypatch)

    run("template", tmp_path, "--write", capsys=capsys)

    assert "pass" not in module.read_text()
    assert render_class(module, "Badge", monkeypatch) == before


def test_template_falls_back_to_single_quotes_when_the_content_has_triple_double(
    tmp_path, monkeypatch, capsys
):
    module = make_card(tmp_path, '<div title=\'"""\'>{{ title }}</div>\n')
    before = render_class(module, "Card", monkeypatch, title="hi")

    code, _ = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert "r'''" in module.read_text()
    assert render_class(module, "Card", monkeypatch, title="hi") == before


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("{# \"\"\" ''' #}<i></i>\n", "both"),
        ("<i></i>{# a \\\n", "backslash"),
        ("  <i></i>\n  <b></b>\n", "indentation"),
    ],
)
def test_template_refuses_content_a_raw_string_cannot_hold(
    tmp_path, capsys, content, reason
):
    module = make_card(tmp_path)
    (tmp_path / "card.pjx").write_text(content)  # unlike write(), keeps indentation
    original = module.read_text()

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert reason in out
    assert module.read_text() == original
    assert (tmp_path / "card.pjx").exists()


def test_template_refuses_a_second_class_of_the_same_name(tmp_path, capsys):
    module = make_card(tmp_path)
    module.write_text(
        module.read_text()
        + "\n\nif True:\n    class Card(BaseComponent):\n        title: str\n"
    )

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "more than one class named Card" in out


def test_template_refuses_a_class_that_already_has_a_template(tmp_path, capsys):
    module = make_card(tmp_path)
    module.write_text(module.read_text() + '\n    template = "<i></i>"\n')

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "already assigns" in out
    assert (tmp_path / "card.pjx").exists()


def test_template_sees_a_template_assigned_alongside_another_name(tmp_path, capsys):
    """Found the way pyjinhx finds it, so the fold never adds a second one."""
    module = make_card(tmp_path)
    module.write_text(module.read_text() + '\n    template = alias = "<i></i>"\n')

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert "already assigns" in out


def test_template_is_idempotent_and_leaves_subclasses_rendering(
    tmp_path, monkeypatch, capsys
):
    module = make_card(tmp_path)
    module.write_text(module.read_text() + "\n\nclass LoudCard(Card):\n    pass\n")
    before = render_class(module, "LoudCard", monkeypatch, title="hi")
    run("template", tmp_path, "--write", capsys=capsys)
    folded = module.read_text()

    code, out = run("template", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert module.read_text() == folded
    assert "0 folded" in out
    assert render_class(module, "LoudCard", monkeypatch, title="hi") == before


def test_template_dry_run_prints_a_diff_and_writes_nothing(tmp_path, capsys):
    module = make_card(tmp_path)

    code, out = run("template", tmp_path, capsys=capsys)

    assert code == 0
    assert module.read_text() == textwrap.dedent(CARD_PY).lstrip("\n")
    assert (tmp_path / "card.pjx").exists()
    assert '+    template = r"""' in out
    assert "+++ /dev/null" in out
    assert "dry run" in out


def test_assets_folds_into_an_inline_template_string(tmp_path, monkeypatch, capsys):
    module = write(tmp_path / "chip.py", CHIP_PY)
    css = write(tmp_path / "chip.css", ".chip { content: '\\2022'; }\n")
    before = render_class(module, "Chip", monkeypatch, label="x")

    code, _ = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert not css.exists()
    ast.parse(module.read_text())
    assert module.read_text().endswith(
        '    template = r"""\n    <i class="chip">{{ label }}</i>\n'
        '    {#css\n    .chip { content: \'\\2022\'; }\n    #}\n    """\n'
    )
    assert render_class(module, "Chip", monkeypatch, label="x") == before


def test_assets_refuses_a_backslash_asset_for_a_non_raw_template(tmp_path, capsys):
    module = write(tmp_path / "chip.py", CHIP_PY.replace('r"""', '"""'))
    css = write(tmp_path / "chip.css", ".chip { content: '\\2022'; }\n")

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "raw" in out
    assert "css" not in module.read_text().split("template")[1]


def test_assets_refuses_a_template_that_is_not_triple_quoted(tmp_path, capsys):
    write(
        tmp_path / "chip.py",
        """
        from pyjinhx import BaseComponent


        class Chip(BaseComponent):
            template = "<i></i>"
        """,
    )
    css = write(tmp_path / "chip.css", ".chip {}\n")

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "triple-quoted" in out


def test_assets_refuses_an_inline_template_that_already_has_the_block(tmp_path, capsys):
    write(
        tmp_path / "chip.py",
        CHIP_PY.replace('    """\n', '    {#css\n    .a {}\n    #}\n    """\n'),
    )
    css = write(tmp_path / "chip.css", ".chip {}\n")

    code, out = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 1
    assert css.exists()
    assert "already" in out


def test_assets_folds_css_and_js_into_one_inline_template(
    tmp_path, monkeypatch, capsys
):
    module = write(tmp_path / "chip.py", CHIP_PY)
    write(tmp_path / "chip.css", ".chip {}\n")
    write(tmp_path / "chip.js", "go();\n")
    before = render_class(module, "Chip", monkeypatch, label="x")

    code, _ = run("assets", tmp_path, "--write", capsys=capsys)

    assert code == 0
    assert render_class(module, "Chip", monkeypatch, label="x") == before
    assert "go();" in before and ".chip {}" in before
