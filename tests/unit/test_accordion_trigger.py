"""PJXAccordionTrigger: the accordion <summary> with auto chevron."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXAccordionTrigger


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def test_renders_summary_with_auto_chevron():
    html = str(PJXAccordionTrigger(id="t", content="Title").render())
    assert "<summary" in html
    assert 'class="pjx-accordion__trigger"' in html
    assert 'id="t"' in html
    assert "pjx-accordion__chevron" in html  # PJXIcon chevron auto-injected
    assert "<svg" in html
    assert "Title" in html


def test_disabled_marks_summary():
    html = str(PJXAccordionTrigger(id="t", disabled=True, content="X").render())
    assert 'aria-disabled="true"' in html
    assert 'tabindex="-1"' in html


def test_actions_wrapper_renders():
    html = str(
        PJXAccordionTrigger(
            id="t",
            content='Title<div class="pjx-accordion__actions"><button>A</button></div>',
        ).render()
    )
    assert 'class="pjx-accordion__actions"' in html
    assert "<button>A</button>" in html
