"""PJXAccordion: the <details> shell that composes trigger + content."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXAccordion, PJXAccordionContent, PJXAccordionTrigger


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _accordion(**kw):
    kw.setdefault(
        "content",
        PJXAccordionTrigger(content="Title").render()
        + PJXAccordionContent(content="<p>body</p>").render(),
    )
    return str(PJXAccordion(id="a", **kw).render())


def test_single_details_root():
    html = _accordion()
    assert html.count("<details") == 1
    assert 'class="pjx-accordion"' in html
    assert 'id="a"' in html


def test_open_default_true():
    assert " open" in _accordion()
    assert " open" not in _accordion(open=False)


def test_group_sets_native_name():
    assert 'name="sidebar"' in _accordion(group="sidebar")


def test_class_name_appends():
    assert 'class="pjx-accordion mine"' in _accordion(class_name="mine")


def test_composition_order_summary_then_body():
    html = _accordion()
    assert html.index("<summary") < html.index("pjx-accordion__content")
    assert "Title" in html
    assert "<p>body</p>" in html


def test_chevron_auto_in_trigger():
    html = _accordion()
    assert "pjx-accordion__chevron" in html
    assert "<svg" in html


def test_clean_break_removed_fields():
    for gone in ("label", "header", "actions", "disabled"):
        assert gone not in PJXAccordion.model_fields
