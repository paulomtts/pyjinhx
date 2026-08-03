"""PJXToastHost — v0.x field/markup parity on the v2 engine.

Ported from v0.x tests/unit/test_toast_host.py, checked against
tests/unit/golden/toast_host.html. The toasts themselves are created client
side by pjx_toast_host.js; the server renders only the empty host container.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_toast_host import PJXToastHost
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    return RenderSession()


def _html(session, **kwargs) -> str:
    base = {"id": "th"}
    base.update(kwargs)
    return render(PJXToastHost(**base), session)  # type: ignore[arg-type]


class TestFields:
    def test_defaults(self):
        host = PJXToastHost(id="th")
        assert host.position == "bottom-right"
        assert host.timeout == 4000
        assert host.dismiss_label == "Dismiss"
        assert host.event_name == "pjx:toast"
        assert host.class_name == ""
        assert host.extra_attrs == {}

    def test_invalid_position_raises(self):
        with pytest.raises(ValidationError):
            PJXToastHost(id="th", position="center")  # type: ignore[arg-type]

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXToastHost(id="th", bogus="x")  # type: ignore[call-arg]


class TestRender:
    def test_default_host_is_an_empty_container(self, session):
        html = _html(session)
        assert html.startswith('<div id="th"')
        assert "pjx-toast-host pjx-toast-host--bottom-right" in html
        assert 'data-event-name="pjx:toast"' in html
        assert 'data-timeout="4000"' in html
        assert 'data-dismiss-label="Dismiss"' in html
        assert html.rstrip().endswith("></div>")

    def test_host_marker_and_aria_wiring(self, session):
        html = _html(session)
        assert "data-pjx-toast-host" in html
        assert 'aria-live="polite"' in html
        assert 'aria-atomic="false"' in html

    def test_configured_props_reach_the_data_attributes(self, session):
        html = _html(
            session,
            position="top-right",
            timeout=2500,
            dismiss_label="Fechar",
            event_name="toast",
        )
        assert "pjx-toast-host--top-right" in html
        assert 'data-timeout="2500"' in html
        assert 'data-dismiss-label="Fechar"' in html
        assert 'data-event-name="toast"' in html

    @pytest.mark.parametrize(
        "position", ["top-right", "top-left", "bottom-right", "bottom-left"]
    )
    def test_each_position_variant_renders_its_modifier(self, session, position):
        assert f"pjx-toast-host--{position}" in _html(session, position=position)

    def test_dismiss_label_is_escaped(self, session):
        html = _html(session, dismiss_label="<b>x</b>")
        assert "<b>x</b>" not in html
        assert "&lt;b&gt;" in html

    def test_class_name_is_appended_to_the_root_class(self, session):
        assert 'class="pjx-toast-host pjx-toast-host--bottom-right dense"' in _html(
            session, class_name="dense"
        )

    def test_extra_attrs_surface_on_the_root(self, session):
        html = _html(session, extra_attrs={"data-k": "v"})
        assert 'data-k="v"' in html[: html.index(">")]

    def test_host_renders_no_toast_markup_server_side(self, session):
        html = _html(session)
        assert "pjx-toast__message" not in html
        assert "pjx-notification" not in html


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXToastHost.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_toast_host.css"
        assert css[0].is_file()

    def test_script_is_frozen_on_the_descriptor(self):
        js = PJXToastHost.__pjx_descriptor__.js_paths
        assert len(js) == 1
        assert js[0].name == "pjx_toast_host.js"
        assert js[0].is_file()

    def test_render_accumulates_both_assets_into_the_session(self, session):
        from pyjinhx.session import accumulate_assets

        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert {p.name for p in session.css_assets} == {"pjx_toast_host.css"}
        assert {p.name for p in session.js_assets} == {"pjx_toast_host.js"}
