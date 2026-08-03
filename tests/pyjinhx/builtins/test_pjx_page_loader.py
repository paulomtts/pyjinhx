"""PJXPageLoader — v0.x field/markup parity on the v2 engine."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.pjx_page_loader import PJXPageLoader
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


class TestFields:
    def test_defaults(self):
        loader = PJXPageLoader(id="pl")
        assert loader.nav_targets == "app-content"
        assert loader.active_on_load is True
        assert loader.loading_label == "Loading"
        assert loader.class_name == ""
        assert loader.extra_attrs == {}

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXPageLoader(id="pl", bogus="x")  # type: ignore[call-arg]


@pytest.fixture
def session():
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "pl"}
    base.update(kwargs)
    return render(PJXPageLoader(**base), session)  # type: ignore[arg-type]


def _root(html: str) -> str:
    return html[: html.index(">") + 1]


class TestRender:
    def test_config_attrs_render_on_the_root(self, session):
        html = _html(
            session, nav_targets="app-content,org-pane", loading_label="Carregando"
        )
        assert 'data-nav-targets="app-content,org-pane"' in html
        assert "pjx-page-loader--active" in _root(html)
        assert 'aria-label="Carregando"' in html

    def test_inactive_on_load_drops_the_active_modifier(self, session):
        assert "pjx-page-loader--active" not in _root(
            _html(session, active_on_load=False)
        )

    def test_root_is_a_single_status_div(self, session):
        html = _html(session)
        root = _root(html)
        assert html.startswith('<div class="pjx-page-loader')
        assert 'id="pl"' in root
        assert "data-pjx-page-loader" in root
        assert 'role="status"' in root
        assert 'aria-live="polite"' in root
        assert html.rstrip().endswith("</div>")

    def test_spinner_child_is_present(self, session):
        assert (
            '<div class="pjx-page-loader__spinner" aria-hidden="true"></div>'
            in _html(session)
        )

    def test_class_name_is_appended_to_the_root_class(self, session):
        assert 'class="pjx-page-loader pjx-page-loader--active compact"' in _html(
            session, class_name="compact"
        )

    def test_extra_attrs_surface_on_the_root(self, session):
        assert 'data-k="v"' in _root(_html(session, extra_attrs={"data-k": "v"}))


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXPageLoader.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_page_loader.css"
        assert css[0].is_file()

    def test_script_is_frozen_on_the_descriptor(self):
        js = PJXPageLoader.__pjx_descriptor__.js_paths
        assert len(js) == 1
        assert js[0].name == "pjx_page_loader.js"
        assert js[0].is_file()

    def test_render_accumulates_both_assets_into_the_session(self, session):
        # RenderSession does not auto-subscribe accumulate_assets — the same
        # explicit wiring test_pjx_region_loader.py uses.
        from pyjinhx.session import accumulate_assets

        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert {p.name for p in session.css_assets} == {"pjx_page_loader.css"}
        assert {p.name for p in session.js_assets} == {"pjx_page_loader.js"}
