import logging
import os
import re
import tempfile

import pytest
from jinja2 import Environment, FileSystemLoader

from pyjinhx import Renderer
from pyjinhx.tags import Parser


def test_plain_html_closing_tags_do_not_warn(caplog):
    html = "<div><span>hi</span><button>x</button></div>"
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        rendered = Renderer.get_default_renderer().render(html)

    assert rendered == html
    assert not caplog.records


def test_plain_html_wrapping_component_does_not_warn(caplog):
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "marker.html"), "w") as file:
            file.write("<span id={{ id }}>{{ text }}</span>\n")

        index_html = '<div><Marker text="New"/></div>'
        with caplog.at_level(logging.WARNING, logger="pyjinhx"):
            rendered = Renderer(
                Environment(loader=FileSystemLoader(temp_dir)),
                auto_id=True,
            ).render(index_html)

    assert re.match(r"^<div><span id=pjx-\d+>New</span></div>$", rendered), (
        f"Output does not match expected pattern. Got: {rendered!r}"
    )
    assert not caplog.records


def test_interleaved_component_close_warns(caplog):
    parser = Parser()
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        parser.feed("<Foo><Bar></Foo>")

    assert any("</foo>" in r.getMessage().lower() for r in caplog.records)
    with pytest.raises(ValueError, match="Unclosed PascalCase component tags"):
        parser.close()
