"""PJXCarousel — v0.x field/markup parity on the v2 engine.

Ported from v0.x tests/unit/test_carousel.py (carousel half) and goldens
carousel_{multi,single,empty,no_loop,autoplay}.html. Slot strings are escaped
here, matching measured pjx_alert/pjx_notification behavior -- tracked as a
pre-existing gap, not fixed by #534.
"""

import pytest
from pydantic import ValidationError

from pyjinhx import discovery
from pyjinhx.builtins.ui.pjx_carousel import PJXCarousel
from pyjinhx.builtins.ui.pjx_carousel_slide import PJXCarouselSlide
from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    # template_dir="/" so the descriptor's absolute template path resolves,
    # same fixture shape as the sibling builtin tests.
    return RenderSession(template_dir="/")


@pytest.fixture
def icon_registered():
    """Publish the ``pjx_icon`` tag for this test only.

    ``<PJXIcon/>`` in pjx_carousel.pjx is resolved at render time through
    discovery's tag map (render.py -> get_class), not through a Python import —
    an unclaimed tag is emitted verbatim as passthrough markup instead. The
    map is process-global, so it is snapshotted and restored rather than left
    mutated for whatever test runs next.
    """
    before = discovery._registry.mapping
    discovery.register_class("pjx_icon", PJXIcon)
    yield
    discovery._registry.mapping = before


def _html(session, **kwargs) -> str:
    base = {"id": "c"}
    base.update(kwargs)
    return render(PJXCarousel(**base), session)  # type: ignore[arg-type]


def _root_tag(html: str) -> str:
    return html[html.index('<div id="c"') :].split(">", 1)[0]


class TestFields:
    def test_defaults(self):
        carousel = PJXCarousel(id="c")
        assert carousel.label == "Carousel"
        assert carousel.loop is True
        assert carousel.autoplay is False
        assert carousel.interval_ms == 5000
        assert carousel.prev_label == "Previous slide"
        assert carousel.next_label == "Next slide"
        assert carousel.autoplay_toggle_label == "Pause autoplay"
        assert carousel.class_name == ""
        assert carousel.content == ""
        assert carousel.extra_attrs == {}

    def test_content_is_the_children_field(self):
        assert PJXCarousel._pjx_children_field == "content"

    def test_content_accepts_a_list_of_slides(self):
        carousel = PJXCarousel(
            id="c",
            content=[PJXCarouselSlide(id="s1"), PJXCarouselSlide(id="s2")],
        )
        assert isinstance(carousel.content, list)
        assert len(carousel.content) == 2

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXCarousel(id="c", bogus="x")  # type: ignore[call-arg]

    def test_non_integer_interval_raises(self):
        with pytest.raises(ValidationError):
            PJXCarousel(id="c", interval_ms="soon")  # type: ignore[arg-type]


class TestRender:
    def test_root_is_a_carousel_region(self, session):
        html = _html(session)
        assert html.startswith('<div id="c" role="region"')
        assert 'aria-roledescription="carousel"' in html
        assert html.rstrip().endswith("</div>")

    def test_default_aria_label(self, session):
        assert 'aria-label="Carousel"' in _html(session)

    def test_custom_aria_label(self, session):
        assert 'aria-label="Product photos"' in _html(session, label="Product photos")

    def test_carousel_marker_attribute_present(self, session):
        assert "data-pjx-carousel" in _root_tag(_html(session))

    def test_loop_attribute_present_by_default(self, session):
        assert "data-pjx-carousel-loop" in _root_tag(_html(session))

    def test_loop_false_omits_the_attribute(self, session):
        assert "data-pjx-carousel-loop" not in _root_tag(_html(session, loop=False))

    def test_autoplay_off_by_default(self, session):
        html = _html(session)
        assert "data-pjx-carousel-autoplay" not in _root_tag(html)
        assert 'class="pjx-carousel__autoplay-toggle"' not in html

    def test_autoplay_emits_attrs_and_toggle(self, session):
        html = _html(session, autoplay=True, interval_ms=3000)
        assert "data-pjx-carousel-autoplay" in _root_tag(html)
        assert 'data-pjx-carousel-interval="3000"' in _root_tag(html)
        assert 'class="pjx-carousel__autoplay-toggle"' in html

    def test_interval_not_emitted_when_autoplay_off(self, session):
        assert "data-pjx-carousel-interval" not in _html(session)

    def test_autoplay_toggle_label_is_used(self, session):
        html = _html(session, autoplay=True, autoplay_toggle_label="Pausar")
        assert 'aria-label="Pausar"' in html

    def test_arrow_buttons_carry_their_labels_and_markers(self, session):
        html = _html(session, prev_label="Anterior", next_label="Proximo")
        assert "data-pjx-carousel-prev" in html
        assert "data-pjx-carousel-next" in html
        assert 'aria-label="Anterior"' in html
        assert 'aria-label="Proximo"' in html

    def test_dots_container_present(self, session):
        assert "data-pjx-carousel-dots" in _html(session)

    def test_track_wraps_a_single_slide(self, session):
        html = _html(session, content=PJXCarouselSlide(id="s1", content="X"))
        start = html.index('class="pjx-carousel__track"')
        assert 'id="s1"' in html
        assert html.index('id="s1"') > start

    def test_track_wraps_multiple_slides(self, session):
        html = _html(
            session,
            content=[PJXCarouselSlide(id="s1"), PJXCarouselSlide(id="s2")],
        )
        assert 'class="pjx-carousel__track"' in html
        assert 'id="s1"' in html
        assert 'id="s2"' in html
        assert html.index('id="s1"') < html.index('id="s2"')

    def test_empty_content_still_renders_the_shell(self, session):
        html = _html(session, content="")
        assert 'class="pjx-carousel__track"' in html
        assert "data-pjx-carousel-dots" in html

    def test_class_name_is_appended_to_the_root_class(self, session):
        assert 'class="pjx-carousel my-gallery"' in _html(
            session, class_name="my-gallery"
        )

    def test_extra_attrs_surface_on_the_root(self, session):
        html = _html(session, extra_attrs={"data-foo": "bar"})
        assert 'data-foo="bar"' in _root_tag(html)

    def test_content_string_is_emitted_raw(self, session):
        # ADR 0003: a plain str in a Slot is authored markup, not escaped.
        html = _html(session, content="<div data-pjx-carousel-slide>X</div>")
        assert "<div data-pjx-carousel-slide>X</div>" in html


class TestIcons:
    def test_arrows_embed_resolved_icons(self, session, icon_registered):
        html = _html(session)
        assert html.count("<svg") == 2
        assert "PJXIcon" not in html

    def test_autoplay_toggle_embeds_pause_and_play_icons(
        self, session, icon_registered
    ):
        html = _html(session, autoplay=True)
        assert "pjx-carousel__autoplay-icon-pause" in html
        assert "pjx-carousel__autoplay-icon-play" in html
        assert html.count("<svg") == 4


@pytest.fixture
def empty_registry():
    """Render with a provably empty tag map — no build_registry(), no setup().

    #693: the arrow and autoplay icons must not depend on registry-based tag
    resolution; an empty map turns any surviving literal into passthrough
    markup and fails these assertions.
    """
    before = discovery._registry.mapping
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = before


class TestIconsWithoutARegistry:
    def test_arrow_icons_render_with_an_empty_registry(self, session, empty_registry):
        html = render(PJXCarousel(id="c", content="slide"), session)
        assert "<PJXIcon" not in html
        assert html.count("<svg") == 2

    def test_autoplay_icons_render_with_an_empty_registry(self, session, empty_registry):
        html = render(PJXCarousel(id="c", content="slide", autoplay=True), session)
        assert "<PJXIcon" not in html
        assert html.count("<svg") == 4
        assert "pjx-carousel__autoplay-icon-pause" in html
        assert "pjx-carousel__autoplay-icon-play" in html

    def test_icon_fields_are_slots(self, empty_registry):
        slots = PJXCarousel.__pjx_descriptor__.slot_fields
        assert {"prev_icon", "next_icon", "pause_icon", "play_icon"} <= slots

    def test_children_field_is_still_content(self, empty_registry):
        assert PJXCarousel.__pjx_descriptor__.children_field == "content"


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXCarousel.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_carousel.css"
        assert css[0].is_file()

    def test_script_is_frozen_on_the_descriptor(self):
        js = PJXCarousel.__pjx_descriptor__.js_paths
        assert len(js) == 1
        assert js[0].name == "pjx_carousel.js"
        assert js[0].is_file()

    def test_script_drives_off_the_carousel_marker(self):
        source = PJXCarousel.__pjx_descriptor__.js_paths[0].read_text()
        assert "data-pjx-carousel" in source

    def test_render_accumulates_both_assets_into_the_session(self, session):
        from pyjinhx.session import accumulate_assets

        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert {p.name for p in session.css_assets} == {"pjx_carousel.css"}
        assert {p.name for p in session.js_assets} == {"pjx_carousel.js"}
