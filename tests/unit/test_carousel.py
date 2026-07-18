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


def _carousel(content=None, **kw):
    if content is None:
        content = _slide("<img src='/a.png'>") + _slide("<img src='/b.png'>")
    return str(PJXCarousel(id="c", content=content, **kw).render())


# --- PJXCarousel ---


def test_carousel_root_div():
    html = _carousel()
    assert '<div id="c"' in html
    assert 'role="region"' in html
    assert 'aria-roledescription="carousel"' in html


def test_carousel_default_label():
    html = _carousel()
    assert 'aria-label="Carousel"' in html


def test_carousel_custom_label():
    html = _carousel(label="Product photos")
    assert 'aria-label="Product photos"' in html


def test_carousel_data_attr():
    html = _carousel()
    assert "data-pjx-carousel" in html


def test_carousel_loop_default_true():
    html = _carousel()
    assert "data-pjx-carousel-loop" in html


def test_carousel_loop_false_omits_attr():
    html = _carousel(loop=False)
    assert "data-pjx-carousel-loop" not in html


def test_carousel_autoplay_default_false_no_toggle():
    html = _carousel()
    assert "data-pjx-carousel-autoplay" not in html
    # The stylesheet unconditionally styles .pjx-carousel__autoplay-toggle (it's
    # always shipped as a static asset), so check for the button markup itself
    # rather than the bare class-name substring, which would also match CSS text.
    assert 'class="pjx-carousel__autoplay-toggle"' not in html


def test_carousel_autoplay_true_emits_attrs_and_toggle():
    html = _carousel(autoplay=True, interval_ms=3000)
    assert "data-pjx-carousel-autoplay" in html
    assert 'data-pjx-carousel-interval="3000"' in html
    assert "pjx-carousel__autoplay-toggle" in html


def test_carousel_track_wraps_content():
    html = _carousel(content="<div data-pjx-carousel-slide>X</div>")
    assert 'class="pjx-carousel__track"' in html
    assert "<div data-pjx-carousel-slide>X</div>" in html


def test_carousel_class_name_appended():
    html = _carousel(class_name="my-gallery")
    assert 'class="pjx-carousel my-gallery"' in html


def test_carousel_inline_attrs_pass_through():
    inline_attrs: dict[str, Any] = {"data-foo": "bar"}
    html = str(PJXCarousel(id="c", content="x", **inline_attrs).render())
    assert 'data-foo="bar"' in html


def test_carousel_empty_content_renders_shell():
    html = _carousel(content="")
    assert 'class="pjx-carousel__track"' in html


def test_carousel_js_asset_exists():
    js_path = _UI / "pjx_carousel" / "pjx-carousel.js"
    assert js_path.exists()
    assert "data-pjx-carousel" in js_path.read_text()


def test_carousel_css_asset_exists():
    css_path = _UI / "pjx_carousel" / "pjx-carousel.css"
    assert css_path.exists()
