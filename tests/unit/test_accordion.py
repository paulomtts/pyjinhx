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


# --- actions slot ---


def test_actions_absent_by_default():
    html = _html(label="X")
    assert '<div class="pjx-accordion__actions">' not in html


def test_actions_rendered_inside_summary():
    html = _html(label="X", actions='<button id="del">Delete</button>')
    assert '<div class="pjx-accordion__actions">' in html
    assert '<button id="del">Delete</button>' in html
    # actions div is inside summary, not inside the body
    summary_end = html.index("</summary>")
    actions_start = html.index("pjx-accordion__actions")
    assert actions_start < summary_end


def test_actions_slot_after_label_in_trigger():
    html = _html(label="Conv", actions='<button>Restore</button>')
    trigger = html[html.index("<summary") : html.index("</summary>") + len("</summary>")]
    assert "Conv" in trigger
    assert "Restore" in trigger
    # label comes before the actions container
    assert trigger.index("Conv") < trigger.index("pjx-accordion__actions")


def test_actions_accepts_component():
    from pyjinhx.builtins import PJXButton

    btn = PJXButton(id="b", label="Delete")
    html = _html(label="X", actions=btn)
    assert "pjx-accordion__actions" in html
    assert "Delete" in html
