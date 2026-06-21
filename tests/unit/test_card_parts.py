"""PJXCardBody / PJXCardFooter: trivial card region wrappers."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXCardBody, PJXCardFooter


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def test_body_renders_single_div():
    html = str(PJXCardBody(id="b", content="<p>hi</p>").render())
    assert html.count("<div") == 1
    assert 'class="pjx-card__body"' in html
    assert 'id="b"' in html
    assert "<p>hi</p>" in html


def test_body_class_name_appends():
    html = str(PJXCardBody(id="b", class_name="tall", content="x").render())
    assert 'class="pjx-card__body tall"' in html


def test_footer_renders_single_footer():
    html = str(PJXCardFooter(id="f", content="Updated").render())
    assert html.count("<footer") == 1
    assert 'class="pjx-card__footer"' in html
    assert 'id="f"' in html
    assert "Updated" in html
