"""The manifest: what an editor learns about components without running them."""

import json
from importlib import resources

import pytest

from pyjinhx import manifest, sfc


def _grammar() -> dict:
    text = resources.files("pyjinhx").joinpath("block_grammar.json").read_text("utf-8")
    return json.loads(text)


def test_the_grammar_ships_as_package_data():
    grammar = _grammar()

    assert grammar["version"] == 1


def test_grammar_flag_prints_the_data_file(capsys):
    assert manifest.main(["--grammar"]) == 0

    assert json.loads(capsys.readouterr().out) == _grammar()


def test_the_grammar_names_exactly_the_keywords_the_scanners_accept():
    assert set(_grammar()["keywords"]) == set(sfc.BLOCK_KEYWORDS)


def test_the_grammar_lists_exactly_the_error_codes_the_scanners_raise():
    assert set(_grammar()["error_codes"]) == {
        sfc.PYTHON_BLOCK_EARLY_CLOSE,
        sfc.SECOND_BLOCK,
        sfc.OPENER_NOT_AT_LINE_START,
        sfc.CLOSER_NOT_AT_LINE_START,
        sfc.UNCLOSED_BLOCK,
        sfc.TEXT_AFTER_CLOSER,
        sfc.STRAY_COMMENT_CLOSE,
    }


@pytest.mark.parametrize("keyword", sfc.BLOCK_KEYWORDS)
def test_each_keyword_follows_the_rule_the_grammar_states(keyword):
    rules = _grammar()["keywords"][keyword]
    one_line = f"{{#{keyword} x #}}\n<p></p>\n"
    spaced = f"{{# {keyword}\nx\n#}}\n<p></p>\n"
    controlled = f"{{#-{keyword}\nx\n#}}\n<p></p>\n"

    def found(source: str) -> bool:
        blocks, _ = manifest.scan_blocks(source, "t.pjx")
        return any(b["keyword"] == keyword for b in blocks)

    assert found(one_line) is (rules["after_keyword"] == "whitespace_or_end")
    assert not found(spaced)
    assert not found(controlled)
