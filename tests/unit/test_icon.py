"""PJXIcon renders a themeable inline SVG from the vendored set."""
from typing import Any

import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXIcon


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _html(**kw):
    return str(PJXIcon(id="i", **kw).render())


def test_renders_single_root_svg_with_currentcolor():
    html = _html(name="plus")
    assert html.count("<svg") == 1
    assert 'stroke="currentColor"' in html
    assert 'fill="none"' in html
    assert '<path d="M5 12h14"' in html  # plus inner markup


def test_int_size_renders_pixels():
    html = _html(name="plus", size=20)
    assert 'width="20px"' in html
    assert 'height="20px"' in html


def test_str_size_renders_verbatim():
    html = _html(name="plus", size="1.5rem")
    assert 'width="1.5rem"' in html


def test_label_sets_role_and_title():
    html = _html(name="search", label="Buscar")
    assert 'role="img"' in html
    assert "<title>Buscar</title>" in html
    assert 'aria-hidden' not in html


def test_no_label_is_aria_hidden():
    html = _html(name="search")
    assert 'aria-hidden="true"' in html
    assert "<title>" not in html


def test_unknown_name_renders_nothing_and_warns(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        html = _html(name="definitely-not-an-icon")
    assert "<svg" not in html
    assert " hidden" in html  # fallback hidden span — renders nothing visible
    assert "<span" in html
    assert any("definitely-not-an-icon" in r.message for r in caplog.records)


def test_inline_attrs_pass_through():
    inline_attrs: dict[str, Any] = {"data-x": "y"}
    html = str(PJXIcon(id="i", name="plus", **inline_attrs).render())
    assert 'data-x="y"' in html
