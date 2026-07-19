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
    root_tag = html[html.index('<div id="c"'):].split(">", 1)[0]
    assert "data-pjx-carousel-loop" in root_tag


def test_carousel_loop_false_omits_attr():
    html = _carousel(loop=False)
    # The inlined pjx-carousel.js controller (auto-appended by the real
    # Renderer environment) contains this literal string in its own source,
    # and asset inlining puts a <style>/<script> block *before* the carousel
    # markup, so locate the carousel's own root <div> rather than assuming
    # it's the first tag in the rendered output.
    root_tag = html[html.index('<div id="c"'):].split(">", 1)[0]
    assert root_tag.startswith('<div id="c"')
    assert "data-pjx-carousel-loop" not in root_tag


def test_carousel_autoplay_default_false_no_toggle():
    html = _carousel()
    # Same reasoning as above: pjx-carousel.js references this attribute name
    # in its own source, and asset inlining precedes the carousel markup, so
    # locate the real root tag rather than assuming it's first in the output.
    root_tag = html[html.index('<div id="c"'):].split(">", 1)[0]
    assert root_tag.startswith('<div id="c"')
    assert "data-pjx-carousel-autoplay" not in root_tag
    # The stylesheet unconditionally styles .pjx-carousel__autoplay-toggle (it's
    # always shipped as a static asset), so check for the button markup itself
    # rather than the bare class-name substring, which would also match CSS text.
    assert 'class="pjx-carousel__autoplay-toggle"' not in html


def test_carousel_autoplay_true_emits_attrs_and_toggle():
    html = _carousel(autoplay=True, interval_ms=3000)
    root_tag = html[html.index('<div id="c"'):].split(">", 1)[0]
    assert root_tag.startswith('<div id="c"')
    assert "data-pjx-carousel-autoplay" in root_tag
    assert 'data-pjx-carousel-interval="3000"' in html
    assert 'class="pjx-carousel__autoplay-toggle"' in html


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
