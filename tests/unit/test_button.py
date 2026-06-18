"""PJXButton: slotted, themeable, structural button."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXButton


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _html(**kw):
    return str(PJXButton(id="b", **kw).render())


def test_single_root_button_with_defaults():
    html = _html(center="Save")
    assert html.count("<button") == 1
    assert 'type="button"' in html
    assert "pjx-button--default" in html
    assert ">Save<" in html


def test_slots_render_and_omit_when_empty():
    html = _html(start="L", center="Mid", end="R")
    assert "pjx-button__start" in html
    assert "pjx-button__center" in html
    assert "pjx-button__end" in html
    html2 = _html(center="Mid")
    assert "pjx-button__start" not in html2
    assert "pjx-button__end" not in html2


def test_variant_and_block_classes():
    html = _html(center="Go", variant="primary", block=True)
    assert "pjx-button--primary" in html
    assert "pjx-button--block" in html


def test_disabled_and_type():
    html = _html(center="X", disabled=True, type="submit")
    assert "disabled" in html
    assert 'type="submit"' in html


def test_loading_composes_region_loader():
    html = _html(center="X", loading=True)
    assert 'aria-busy="true"' in html
    assert "pjx-region-loader" in html


def test_inline_attrs_pass_through():
    html = str(PJXButton(id="b", center="X", **{"hx-post": "/save"}).render())
    assert 'hx-post="/save"' in html
