"""PJXCarouselSlide — v0.x field/markup parity on the v2 engine.

Ported from v0.x tests/unit/test_carousel.py (slide half) and golden
carousel_slide.html. Slot strings are escaped here, matching measured
pjx_alert/pjx_notification behavior -- PjxSlot's docstring and ADR 0003 both
describe plain-string slots as raw-HTML-capable, which the implementation does
not currently honor; tracked as a pre-existing gap, not fixed by #534.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_carousel_slide import PJXCarouselSlide
from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    # template_dir="/" so the descriptor's absolute template path resolves,
    # same fixture shape as the sibling builtin tests.
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "s1"}
    base.update(kwargs)
    return render(PJXCarouselSlide(**base), session)  # type: ignore[arg-type]


class TestFields:
    def test_defaults(self):
        slide = PJXCarouselSlide(id="s1")
        assert slide.label == ""
        assert slide.class_name == ""
        assert slide.content == ""
        assert slide.extra_attrs == {}

    def test_content_is_the_children_field(self):
        assert PJXCarouselSlide._pjx_children_field == "content"

    def test_content_accepts_a_component(self):
        slide = PJXCarouselSlide(id="s1", content=PJXDivider(id="d"))
        assert isinstance(slide.content, PJXDivider)

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXCarouselSlide(id="s1", bogus="x")  # type: ignore[call-arg]


class TestRender:
    def test_root_is_a_group_div(self, session):
        html = _html(session)
        assert html.startswith('<div id="s1" role="group"')
        assert 'class="pjx-carousel__slide"' in html
        assert html.rstrip().endswith("</div>")

    def test_slide_marker_attribute_present(self, session):
        assert "data-pjx-carousel-slide" in _html(session)

    def test_label_sets_aria_label_and_data_label(self, session):
        html = _html(session, label="Product photo 2")
        assert 'aria-label="Product photo 2"' in html
        assert 'data-pjx-carousel-label="Product photo 2"' in html

    def test_no_label_omits_aria_label(self, session):
        assert "aria-label" not in _html(session)

    def test_class_name_is_appended_to_the_root_class(self, session):
        assert 'class="pjx-carousel__slide my-slide"' in _html(
            session, class_name="my-slide"
        )

    def test_content_lands_inside_the_slide(self, session):
        assert ">Bridge</div>" in _html(session, content="Bridge")

    def test_content_string_is_emitted_raw(self, session):
        # ADR 0003: a plain str in a Slot is authored markup, not escaped.
        html = _html(session, content="<img src='/a.png'>")
        assert "<img src='/a.png'>" in html

    def test_component_content_renders_nested(self, session):
        assert 'id="d"' in _html(session, content=PJXDivider(id="d"))

    def test_extra_attrs_surface_on_the_root(self, session):
        html = _html(session, extra_attrs={"data-foo": "bar"})
        assert 'data-foo="bar"' in html[: html.index(">")]


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXCarouselSlide.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_carousel_slide.css"
        assert css[0].is_file()

    def test_no_script_asset(self):
        assert PJXCarouselSlide.__pjx_descriptor__.js_paths == ()

    def test_render_accumulates_the_stylesheet_into_the_session(self, session):
        from pyjinhx.session import accumulate_assets

        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert {p.name for p in session.css_assets} == {"pjx_carousel_slide.css"}
