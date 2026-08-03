"""PJXNotification — v0.x field/markup parity on the v2 engine.

Ported from v0.x tests/unit/test_notification_redesign.py and checked against
tests/unit/golden/notification.html. Slot strings are escaped here, matching
measured pjx_empty_state behavior -- PjxSlot's docstring and ADR 0003 both
describe plain-string slots as raw-HTML-capable, which the implementation
does not currently honor; tracked as a pre-existing gap, not fixed by #532.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.builtins.ui.pjx_notification import PJXNotification
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    # template_dir="/" so the descriptor's absolute template path resolves,
    # same fixture shape as tests/pyjinhx/builtins/test_pjx_region_loader.py.
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "n1"}
    base.update(kwargs)
    return render(PJXNotification(**base), session)  # type: ignore[arg-type]


class TestFields:
    def test_defaults(self):
        note = PJXNotification(id="n1")
        assert note.content == ""
        assert note.corner == "top-right"
        assert note.timeout == 5000
        assert note.autoshow is True
        assert note.dismiss_label == "Dismiss"
        assert note.class_name == ""
        assert note.extra_attrs == {}

    def test_content_accepts_a_component(self):
        note = PJXNotification(id="n1", content=PJXDivider(id="d"))
        assert isinstance(note.content, PJXDivider)

    def test_invalid_corner_raises(self):
        with pytest.raises(ValidationError):
            PJXNotification(id="n1", corner="middle")  # type: ignore[arg-type]

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXNotification(id="n1", bogus="x")  # type: ignore[call-arg]


class TestRender:
    def test_root_carries_the_status_role_and_corner_class(self, session):
        html = _html(session)
        assert html.startswith(
            '<div class="pjx-notification pjx-notification--top-right" id="n1"'
        )
        assert 'role="status"' in html
        assert 'aria-live="polite"' in html
        assert 'data-timeout="5000"' in html
        assert html.rstrip().endswith("</div>")

    @pytest.mark.parametrize(
        "corner", ["top-right", "top-left", "bottom-right", "bottom-left"]
    )
    def test_each_corner_variant_renders_its_modifier(self, session, corner):
        assert f"pjx-notification--{corner}" in _html(session, corner=corner)

    def test_autoshow_marker_present_by_default(self, session):
        assert "data-pjx-autoshow" in _html(session)

    def test_autoshow_marker_absent_when_disabled(self, session):
        assert "data-pjx-autoshow" not in _html(session, autoshow=False)

    def test_close_button_is_declarative(self, session):
        html = _html(session, dismiss_label="Fechar")
        assert 'class="pjx-notification__close"' in html
        assert "data-pjx-close" in html
        assert 'aria-label="Fechar"' in html
        assert "onclick" not in html

    def test_content_lands_in_the_content_slot(self, session):
        html = _html(session, content="Saved")
        assert '<div class="pjx-notification__content">Saved</div>' in html

    def test_content_string_is_emitted_escaped(self, session):
        html = _html(session, content="<b>x</b>")
        assert "<b>x</b>" not in html
        assert "&lt;b&gt;x&lt;/b&gt;" in html

    def test_component_content_renders_nested(self, session):
        html = _html(session, content=PJXDivider(id="d"))
        assert 'class="pjx-notification__content">' in html
        assert 'id="d"' in html

    def test_dismiss_label_is_escaped(self, session):
        html = _html(session, dismiss_label='a"b<c')
        assert 'a"b<c' not in html
        assert "&lt;c" in html

    def test_class_name_is_appended_to_the_root_class(self, session):
        assert 'class="pjx-notification pjx-notification--top-right compact"' in _html(
            session, class_name="compact"
        )

    def test_extra_attrs_surface_on_the_root(self, session):
        html = _html(session, extra_attrs={"data-k": "v"})
        assert 'data-k="v"' in html[: html.index(">")]


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXNotification.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_notification.css"
        assert css[0].is_file()

    def test_script_is_frozen_on_the_descriptor(self):
        js = PJXNotification.__pjx_descriptor__.js_paths
        assert len(js) == 1
        assert js[0].name == "pjx_notification.js"
        assert js[0].is_file()

    def test_render_accumulates_both_assets_into_the_session(self, session):
        from pyjinhx.session import accumulate_assets

        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert {p.name for p in session.css_assets} == {"pjx_notification.css"}
        assert {p.name for p in session.js_assets} == {"pjx_notification.js"}
