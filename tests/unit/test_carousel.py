"""PJXCarousel / PJXCarouselSlide: image/content carousel with arrows, dots,
keyboard nav, swipe, and opt-in accessible autoplay."""
from pathlib import Path
from typing import Any

import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXCarousel, PJXCarouselSlide

_UI = Path(__file__).resolve().parents[2] / "pyjinhx" / "builtins" / "ui"


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _slide(content="<img src='/a.png'>", **kw):
    return PJXCarouselSlide(content=content, **kw).render()


# --- PJXCarouselSlide ---


def test_slide_root_div():
    html = str(_slide())
    assert '<div id="' in html
    assert 'role="group"' in html
    assert 'class="pjx-carousel__slide"' in html


def test_slide_data_attr():
    html = str(_slide())
    assert "data-pjx-carousel-slide" in html


def test_slide_content_rendered():
    html = str(_slide(content="<img src='/photo.jpg' alt='Bridge'>"))
    assert "<img src='/photo.jpg' alt='Bridge'>" in html


def test_slide_label_sets_aria_label():
    html = str(_slide(label="Product photo 2"))
    assert 'aria-label="Product photo 2"' in html


def test_slide_no_label_omits_aria_label():
    html = str(_slide())
    assert "aria-label" not in html


def test_slide_class_name_appended():
    html = str(_slide(class_name="my-slide"))
    assert 'class="pjx-carousel__slide my-slide"' in html


def test_slide_inline_attrs_pass_through():
    inline_attrs: dict[str, Any] = {"data-foo": "bar"}
    html = str(PJXCarouselSlide(content="x", **inline_attrs).render())
    assert 'data-foo="bar"' in html
