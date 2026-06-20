"""Builtins pass stray tag attributes through to their root element."""

from typing import Any

import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXModal, PJXPopoverPanel, PJXPopoverTrigger


def test_tag_attrs_pass_through_to_builtin_root(tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    rendered = renderer.render(
        '<PJXPopoverTrigger id="t" title="hello" data-action="x">go</PJXPopoverTrigger>'
    )

    assert 'title="hello"' in rendered
    assert 'data-action="x"' in rendered
    assert ">go</button>" in rendered


def test_extra_attrs_with_double_quotes_render_single_quoted(tmp_path):
    Renderer.set_default_environment(str(tmp_path))

    html = str(
        PJXPopoverPanel(
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
        """<PJXPopoverPanel id="pp" hx-headers='{"X-CSRF-Token": "t"}'>x</PJXPopoverPanel>"""
    )

    assert "hx-headers='{\"X-CSRF-Token\": \"t\"}'" in rendered


def test_extra_attrs_value_with_both_quote_types_raises():
    with pytest.raises(ValueError, match="both"):
        PJXModal(id="m", extra_attrs={"data-x": "a\"b'c"})


def test_stray_attr_with_both_quote_types_raises_at_render(tmp_path):
    Renderer.set_default_environment(str(tmp_path))

    inline_attrs: dict[str, Any] = {"data-x": "a\"b'c"}
    with pytest.raises(ValueError, match="both"):
        str(PJXPopoverTrigger(id="t", content="go", **inline_attrs).render())
