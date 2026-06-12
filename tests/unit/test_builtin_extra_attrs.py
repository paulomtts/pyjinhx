"""Builtins pass stray tag attributes through to their root element."""

import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import Modal, PopoverPanel, PopoverTrigger


def test_tag_attrs_pass_through_to_builtin_root(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    rendered = renderer.render(
        '<PopoverTrigger id="t" title="hello" data-action="x">go</PopoverTrigger>'
    )

    assert 'title="hello"' in rendered
    assert 'data-action="x"' in rendered
    assert ">go</button>" in rendered


def test_extra_attrs_with_double_quotes_render_single_quoted(tmp_path):
    Renderer.set_default_environment(str(tmp_path))

    html = str(
        PopoverPanel(
            id="pp",
            content="x",
            extra_attrs={"hx-headers": '{"X-CSRF-Token": "t"}'},
        ).render()
    )

    assert "hx-headers='{\"X-CSRF-Token\": \"t\"}'" in html


def test_tag_attr_with_double_quotes_survives_full_render(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    rendered = renderer.render(
        """<PopoverPanel id="pp" hx-headers='{"X-CSRF-Token": "t"}'>x</PopoverPanel>"""
    )

    assert "hx-headers='{\"X-CSRF-Token\": \"t\"}'" in rendered


def test_extra_attrs_value_with_both_quote_types_raises():
    with pytest.raises(ValueError, match="both"):
        Modal(id="m", extra_attrs={"data-x": "a\"b'c"})


def test_stray_attr_with_both_quote_types_raises_at_render(tmp_path):
    Renderer.set_default_environment(str(tmp_path))

    with pytest.raises(ValueError, match="both"):
        str(PopoverTrigger(id="t", content="go", **{"data-x": "a\"b'c"}).render())
