"""PJXAccordion: native <details> collapsible composing PJXIcon chevron."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXAccordion


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _html(**kw):
    return str(PJXAccordion(id="a", **kw).render())


def test_single_root_details_with_summary_and_body():
    html = _html(label="Today", content="<p>items</p>")
    assert html.count("<details") == 1
    assert "<summary" in html
    assert "pjx-accordion__body" in html
    assert "<p>items</p>" in html
    assert "Today" in html


def test_open_attribute_default_true():
    assert " open" in _html(label="X")
    assert " open" not in _html(label="X", open=False)


def test_chevron_composes_pjx_icon():
    html = _html(label="X")
    assert "pjx-accordion__chevron" in html
    assert "<svg" in html  # PJXIcon rendered


def test_group_sets_native_name():
    html = _html(label="X", group="sidebar")
    assert 'name="sidebar"' in html


def test_header_slot_wins_over_label():
    html = _html(label="plain", header="<b>Rich</b>")
    assert "<b>Rich</b>" in html
    assert "plain" not in html


def test_disabled_marks_summary():
    html = _html(label="X", disabled=True)
    assert 'aria-disabled="true"' in html
    assert 'tabindex="-1"' in html


def test_inline_attrs_pass_through():
    html = str(PJXAccordion(id="a", label="X", **{"data-y": "z"}).render())
    assert 'data-y="z"' in html
