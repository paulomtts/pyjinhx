"""PJXAccordionContent: the accordion body <div>."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXAccordionContent


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def test_renders_single_content_div():
    html = str(PJXAccordionContent(id="c", content="<p>hi</p>").render())
    assert html.count("<div") == 1
    assert 'class="pjx-accordion__content"' in html
    assert 'id="c"' in html
    assert "<p>hi</p>" in html


def test_class_name_appends():
    html = str(PJXAccordionContent(id="c", class_name="tall", content="x").render())
    assert 'class="pjx-accordion__content tall"' in html
