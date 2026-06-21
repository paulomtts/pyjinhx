"""PJXButton: freeform {{ content }} slot, themeable, structural button."""
from typing import Any

import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXButton


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _html(**kw):
    return str(PJXButton(id="b", **kw).render())


def test_single_root_button_with_defaults():
    html = _html(content="Save")
    assert html.count("<button") == 1
    assert 'type="button"' in html
    assert "pjx-button--default" in html
    assert "Save" in html


def test_content_renders_inside_button():
    html = _html(content="Save")
    assert "Save" in html
    # no slot spans — content goes directly into <button>
    assert "pjx-button__" not in html


def test_removed_fields_gone_from_model():
    assert "start" not in PJXButton.model_fields
    assert "center" not in PJXButton.model_fields
    assert "end" not in PJXButton.model_fields
    assert "content" in PJXButton.model_fields


def test_variant_and_block_classes():
    html = _html(content="Go", variant="primary", block=True)
    assert "pjx-button--primary" in html
    assert "pjx-button--block" in html


def test_disabled_and_type():
    html = _html(content="X", disabled=True, type="submit")
    assert "disabled" in html
    assert 'type="submit"' in html


def test_loading_composes_region_loader():
    html = _html(content="X", loading=True)
    assert 'aria-busy="true"' in html
    assert "pjx-region-loader" in html


def test_loading_appends_loader_after_content():
    html = _html(content="Save", loading=True)
    # find the <button> tag then check ordering within it
    btn_start = html.index("<button")
    content_pos = html.index("Save", btn_start)
    loader_pos = html.index("pjx-region-loader", btn_start)
    assert content_pos < loader_pos


def test_class_name_appends():
    html = _html(content="X", class_name="my-btn")
    assert "my-btn" in html


def test_inline_attrs_pass_through():
    inline_attrs: dict[str, Any] = {"hx-post": "/save"}
    html = str(PJXButton(id="b", content="X", **inline_attrs).render())
    assert 'hx-post="/save"' in html
