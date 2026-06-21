"""PJXCardHeader: <header> with a title convenience falling back to content."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXCardHeader


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def test_title_renders_styled_h3():
    html = str(PJXCardHeader(id="h", title="Q3 report").render())
    assert html.count("<header") == 1
    assert 'class="pjx-card__header"' in html
    assert 'id="h"' in html
    assert '<h3 class="pjx-card__title">Q3 report</h3>' in html


def test_content_used_when_no_title():
    html = str(PJXCardHeader(id="h", content="<span>Rich</span>").render())
    assert "<span>Rich</span>" in html
    assert '<h3 class="pjx-card__title">' not in html


def test_title_wins_over_content():
    html = str(PJXCardHeader(id="h", title="T", content="<span>x</span>").render())
    assert '<h3 class="pjx-card__title">T</h3>' in html
    assert ">x</span>" not in html


def test_class_name_appends():
    html = str(PJXCardHeader(id="h", class_name="lead", content="x").render())
    assert 'class="pjx-card__header lead"' in html
