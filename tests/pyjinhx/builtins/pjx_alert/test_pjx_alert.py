"""PJXAlert — v0.x field/markup parity on the v2 engine.

Ported from v0.x tests/unit/test_alert_dismiss.py. Slot strings are escaped
here, matching measured pjx_notification/pjx_empty_state behavior -- PjxSlot's
docstring and ADR 0003 both describe plain-string slots as raw-HTML-capable,
which the implementation does not currently honor; tracked as a pre-existing
gap, not fixed by #533.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_alert import PJXAlert
from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    # template_dir="/" so the descriptor's absolute template path resolves,
    # same fixture shape as tests/pyjinhx/builtins/pjx_notification.
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "a1"}
    base.update(kwargs)
    return render(PJXAlert(**base), session)  # type: ignore[arg-type]


class TestFields:
    def test_defaults(self):
        alert = PJXAlert(id="a1")
        assert alert.variant == "info"
        assert alert.title == ""
        assert alert.body == ""
        assert alert.dismissible is False
        assert alert.dismiss_label == "Dismiss"
        assert alert.class_name == ""
        assert alert.extra_attrs == {}

    def test_body_is_the_children_field(self):
        assert PJXAlert._pjx_children_field == "body"

    def test_body_accepts_a_component(self):
        alert = PJXAlert(id="a1", body=PJXDivider(id="d"))
        assert isinstance(alert.body, PJXDivider)

    def test_invalid_variant_raises(self):
        with pytest.raises(ValidationError):
            PJXAlert(id="a1", variant="fatal")  # type: ignore[arg-type]

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXAlert(id="a1", bogus="x")  # type: ignore[call-arg]


class TestRender:
    def test_root_carries_the_status_role_and_variant_class(self, session):
        html = _html(session)
        assert html.startswith('<div class="pjx-alert pjx-alert--info" id="a1"')
        assert 'role="status"' in html
        assert html.rstrip().endswith("</div>")

    @pytest.mark.parametrize("variant", ["info", "success", "warning", "error"])
    def test_each_variant_renders_its_modifier(self, session, variant):
        assert f"pjx-alert--{variant}" in _html(session, variant=variant)

    def test_title_renders_when_set(self, session):
        html = _html(session, title="Heads up")
        assert '<div class="pjx-alert__title">Heads up</div>' in html

    def test_title_block_absent_when_empty(self, session):
        assert "pjx-alert__title" not in _html(session)

    def test_body_lands_in_the_body_slot(self, session):
        assert '<div class="pjx-alert__body">Saved</div>' in _html(
            session, body="Saved"
        )

    def test_body_string_is_emitted_raw(self, session):
        # ADR 0003: a plain str in a Slot is authored markup, not escaped.
        html = _html(session, body="<b>x</b>")
        assert "<b>x</b>" in html

    def test_component_body_renders_nested(self, session):
        html = _html(session, body=PJXDivider(id="d"))
        assert 'class="pjx-alert__body">' in html
        assert 'id="d"' in html

    def test_dismiss_button_is_declarative(self, session):
        html = _html(session, dismissible=True, dismiss_label="Fechar")
        assert 'class="pjx-alert__dismiss"' in html
        assert "data-pjx-close" in html
        assert 'aria-label="Fechar"' in html
        assert "onclick" not in html

    def test_dismiss_button_absent_by_default(self, session):
        assert "data-pjx-close" not in _html(session)

    def test_class_name_is_appended_to_the_root_class(self, session):
        assert "pjx-alert--info mine" in _html(session, class_name="mine")

    def test_extra_attrs_surface_on_the_root(self, session):
        html = _html(session, extra_attrs={"data-k": "v"})
        assert 'data-k="v"' in html[: html.index(">")]

    def test_v0x_dismiss_parity(self, session):
        html = _html(
            session,
            body="x",
            dismissible=True,
            dismiss_label="Fechar",
            class_name="mine",
            extra_attrs={"data-k": "v"},
        )
        assert 'aria-label="Fechar"' in html
        assert "data-pjx-close" in html
        assert "onclick" not in html
        assert 'data-k="v"' in html
        assert "pjx-alert--info mine" in html


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXAlert.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_alert.css"
        assert css[0].is_file()

    def test_script_is_frozen_on_the_descriptor(self):
        js = PJXAlert.__pjx_descriptor__.js_paths
        assert len(js) == 1
        assert js[0].name == "pjx_alert.js"
        assert js[0].is_file()

    def test_render_accumulates_both_assets_into_the_session(self, session):
        from pyjinhx.session import accumulate_assets

        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert {p.name for p in session.css_assets} == {"pjx_alert.css"}
        assert {p.name for p in session.js_assets} == {"pjx_alert.js"}
