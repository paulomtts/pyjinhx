"""PJXRegionLoader — v0.x field/markup parity on the v2 engine."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.pjx_region_loader import PJXRegionLoader
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


class TestFields:
    def test_defaults(self):
        loader = PJXRegionLoader(id="rl")
        assert loader.aria_label == "Loading"
        assert loader.class_name == ""
        assert loader.extra_attrs == {}

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXRegionLoader(id="rl", bogus="x")  # type: ignore[call-arg]


@pytest.fixture
def session():
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "rl"}
    base.update(kwargs)
    return render(PJXRegionLoader(**base), session)  # type: ignore[arg-type]


class TestRender:
    def test_root_is_a_single_status_div(self, session):
        html = _html(session)
        assert html.startswith('<div class="pjx-region-loader" id="rl"')
        assert 'role="status"' in html
        assert 'aria-label="Loading"' in html
        assert 'aria-live="polite"' in html
        assert html.rstrip().endswith("</div>")

    def test_spinner_child_is_present(self, session):
        assert '<div class="pjx-region-loader__spinner"></div>' in _html(session)

    def test_custom_aria_label(self, session):
        assert 'aria-label="Saving"' in _html(session, aria_label="Saving")

    def test_class_name_is_appended_to_the_root_class(self, session):
        assert 'class="pjx-region-loader compact"' in _html(
            session, class_name="compact"
        )

    def test_extra_attrs_surface_on_the_root(self, session):
        html = _html(session, extra_attrs={"data-k": "v"})
        assert 'data-k="v"' in html[: html.index(">")]


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXRegionLoader.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_region_loader.css"
        assert css[0].is_file()

    def test_script_is_frozen_on_the_descriptor(self):
        js = PJXRegionLoader.__pjx_descriptor__.js_paths
        assert len(js) == 1
        assert js[0].name == "pjx_region_loader.js"
        assert js[0].is_file()

    def test_render_accumulates_both_assets_into_the_session(self, session):
        # RenderSession does not auto-subscribe accumulate_assets — the same
        # explicit wiring test_pjx_lazy_load.py uses.
        from pyjinhx.session import accumulate_assets

        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert {p.name for p in session.css_assets} == {"pjx_region_loader.css"}
        assert {p.name for p in session.js_assets} == {"pjx_region_loader.js"}
