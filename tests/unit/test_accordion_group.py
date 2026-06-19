"""PJXAccordionGroup: wraps PJXAccordions in a shared layout/behavior container."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXAccordion, PJXAccordionGroup


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _group(**kw):
    return str(PJXAccordionGroup(id="g", **kw).render())


def _accordion(**kw):
    return str(PJXAccordion(**kw).render())


def test_single_root_div():
    html = _group()
    assert "<div" in html
    assert 'class="pjx-accordion-group"' in html


def test_data_pjx_accordion_group_attr():
    html = _group()
    assert "data-pjx-accordion-group" in html


def test_default_mode_is_multi():
    html = _group()
    assert 'data-mode="multi"' in html


def test_exclusive_mode_attr():
    html = _group(mode="exclusive")
    assert 'data-mode="exclusive"' in html


def test_gap_propagated_as_css_var():
    html = _group(gap="1rem")
    assert "--pjx-accordion-group-gap: 1rem" in html


def test_gap_default_zero():
    html = _group()
    assert "--pjx-accordion-group-gap: 0" in html


def test_class_name_appended():
    html = _group(class_name="my-stack")
    assert 'class="pjx-accordion-group my-stack"' in html


def test_children_rendered_in_content():
    inner = _accordion(id="a1", label="Item", content="<p>body</p>")
    html = _group(content=inner)
    assert "pjx-accordion" in html
    assert "<p>body</p>" in html


def test_inline_attrs_pass_through():
    html = str(PJXAccordionGroup(id="g", **{"data-foo": "bar"}).render())
    assert 'data-foo="bar"' in html


# --- default_open ---


def test_default_open_default_is_none():
    html = _group()
    assert "data-default-open" not in html


def test_default_open_none_emits_no_attr():
    html = _group(default_open="none")
    assert "data-default-open" not in html


def test_default_open_first_emits_attr():
    html = _group(default_open="first")
    assert 'data-default-open="first"' in html


def test_default_open_all_emits_attr():
    html = _group(default_open="all")
    assert 'data-default-open="all"' in html
