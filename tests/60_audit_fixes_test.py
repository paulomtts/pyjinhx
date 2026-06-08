import pytest

from pyjinhx.core.finder import Finder
from pyjinhx.core.parser import Parser


def test_parser_raises_on_unclosed_custom_tag():
    parser = Parser()
    parser.feed("<MyWidget><Inner>")
    with pytest.raises(ValueError, match="Unclosed PascalCase"):
        parser.close()


def test_parser_preserves_html_comment():
    parser = Parser()
    parser.feed("<!-- note --><Button id='a'/>")
    parser.close()
    assert any(isinstance(node, str) and "<!-- note -->" in node for node in parser.root_nodes)


def test_finder_raises_on_ambiguous_filename(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "widget.html").write_text("<div>a</div>")
    (tmp_path / "b" / "widget.html").write_text("<div>b</div>")
    finder = Finder(root=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="Ambiguous template name 'widget.html'"):
        finder.find("widget.html")
