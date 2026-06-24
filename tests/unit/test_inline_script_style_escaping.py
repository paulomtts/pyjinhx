"""Regression tests for #177.

Python's ``html.parser.HTMLParser`` treats ``<script>`` and ``<style>`` as
raw-text (CDATA) elements and still delivers their bodies through
``handle_data``. The #120 round-trip re-escaping in ``Parser.handle_data`` must
NOT touch those bodies — escaping ``"`` → ``&#34;``, ``&`` → ``&amp;``,
``<`` → ``&lt;`` corrupts the JavaScript/CSS and the browser throws
``Uncaught SyntaxError``.

Tag expansion only runs when the markup contains a PascalCase component tag
(otherwise ``expand_custom_tags`` returns the markup untouched), so every
end-to-end case here pairs the inline ``<script>``/``<style>`` with a ``<Marker>``
tag to force the parser to run.
"""

import os
import tempfile

from jinja2 import Environment, FileSystemLoader

from pyjinhx import Renderer
from pyjinhx.tags import Parser


def _render_with_marker(index_html: str) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "marker.html"), "w") as file:
            file.write("<span id={{ id }}>{{ text }}</span>\n")
        return Renderer(
            Environment(loader=FileSystemLoader(temp_dir)),
            auto_id=True,
        ).render(index_html)


def test_inline_script_body_not_escaped_through_tag_expansion():
    index = (
        '<div><Marker text="hi"/></div>'
        '<script>var KEY = "sidebarOpen"; if (a && b < c) doThing();</script>'
    )
    html = _render_with_marker(index)
    assert 'var KEY = "sidebarOpen";' in html
    assert "if (a && b < c) doThing();" in html
    for bad in ("&#34;", "&amp;&amp;", "&lt;"):
        assert bad not in html, f"script body was HTML-escaped: found {bad!r}"


def test_inline_style_body_not_escaped_through_tag_expansion():
    index = '<div><Marker text="hi"/></div><style>.x::before{content:"&"}</style>'
    html = _render_with_marker(index)
    assert '.x::before{content:"&"}' in html
    assert "&#34;" not in html
    assert "&amp;" not in html


def test_ordinary_text_still_escaped_through_tag_expansion():
    """Guards the #120 behaviour: ordinary text data outside raw-text elements
    is still escaped, so an autoescaped scalar cannot smuggle live markup back
    through the tag-expansion round-trip."""
    index = '<div><Marker text="hi"/></div><p>plain & text</p>'
    html = _render_with_marker(index)
    assert "plain &amp; text" in html


def test_parser_keeps_script_body_raw():
    """Root-cause lock at the parser level: a raw-text element body is appended
    verbatim while ordinary data is still escaped."""
    parser = Parser()
    parser.feed("<Foo/><script>a && b < c</script><p>x & y</p>")
    parser.close()
    out = "".join(node for node in parser.root_nodes if isinstance(node, str))
    assert "<script>a && b < c</script>" in out  # raw-text body untouched
    assert "x &amp; y" in out  # ordinary text still escaped
