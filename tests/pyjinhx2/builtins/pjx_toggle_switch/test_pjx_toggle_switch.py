"""PJXToggleSwitch — v0.x field/markup parity on the v2 engine.

Partial port of tests/unit/test_toggle_segmented.py: only the
``test_toggle_switch_*`` cases carry over here; the PJXSegmentedControl cases in
that same file live in tests/pyjinhx2/builtins/pjx_segmented_control/. v0.x's
golden-snapshot comparison does not carry over either — v2 builtins assert on
rendered substrings, like every sibling port.
"""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.ui.pjx_toggle_switch import PJXToggleSwitch
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as the sibling builtin tests.
    """
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "ts", "name": "notify"}
    base.update(kwargs)
    return render(PJXToggleSwitch(**base), session)  # type: ignore[arg-type]


def _root(html: str) -> str:
    return html[: html.index(">")]


class TestFields:
    def test_defaults(self):
        switch = PJXToggleSwitch(id="ts")
        assert switch.name == ""
        assert switch.value == "on"
        assert switch.checked is False
        assert switch.label == ""
        assert switch.disabled is False
        assert switch.class_name == ""
        assert switch.extra_attrs == {}

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXToggleSwitch(id="ts", bogus="x")  # type: ignore[call-arg]

    def test_inline_attr_kwargs_no_longer_pass_through(self):
        """v0.x accepted ``PJXToggleSwitch(..., **{"data-test": "1"})``.

        v2 core is strict (extra="forbid"), so a bare inline attr kwarg is now a
        ValidationError. The behavior it replaces is not dropped: pass-through
        moved to the declared ``extra_attrs`` mapping, covered by
        TestRender.test_extra_attrs_surface_on_the_root.
        """
        with pytest.raises(ValidationError):
            PJXToggleSwitch(id="ts", **{"data-test": "1"})  # type: ignore[arg-type]


class TestRender:
    def test_single_root_label(self, session):
        html = _html(session).strip()
        assert html.startswith('<label id="ts"')
        assert html.endswith("</label>")
        assert html.count("<label") == 1

    def test_checkbox_input_present(self, session):
        assert 'type="checkbox"' in _html(session)
        assert "pjx-toggle-switch__input" in _html(session)

    def test_name_attr_rendered(self, session):
        assert 'name="notify"' in _html(session)

    def test_no_name_attr_when_name_is_empty(self, session):
        assert ' name="' not in _html(session, name="")

    def test_value_attr_defaults_to_on(self, session):
        assert 'value="on"' in _html(session)

    def test_value_attr_reflects_field(self, session):
        assert 'value="yes"' in _html(session, value="yes")

    def test_checked_adds_checked_attr(self, session):
        assert " checked" in _html(session, checked=True)

    def test_unchecked_omits_checked_attr(self, session):
        assert " checked" not in _html(session)

    def test_disabled_adds_disabled_attr(self, session):
        assert " disabled" in _html(session, disabled=True)

    def test_not_disabled_by_default(self, session):
        assert " disabled" not in _html(session)

    def test_track_and_thumb_are_always_present(self, session):
        html = _html(session)
        assert "pjx-toggle-switch__track" in html
        assert "pjx-toggle-switch__thumb" in html

    def test_label_span_present_when_label_is_set(self, session):
        html = _html(session, label="Notify me")
        assert "pjx-toggle-switch__label" in html
        assert ">Notify me</span>" in html

    def test_no_label_span_when_label_is_empty(self, session):
        assert "pjx-toggle-switch__label" not in _html(session)

    def test_label_text_renders_escaped(self, session):
        html = _html(session, label="<script>x</script>")
        assert "&lt;script&gt;x&lt;/script&gt;" in html
        assert "<script>" not in html

    def test_class_name_is_appended_without_clobbering_base_classes(self, session):
        assert 'class="pjx-toggle-switch my-ts"' in _html(session, class_name="my-ts")

    def test_empty_class_name_adds_nothing(self, session):
        assert 'class="pjx-toggle-switch"' in _html(session)

    def test_extra_attrs_surface_on_the_root(self, session):
        assert 'data-test="1"' in _root(_html(session, extra_attrs={"data-test": "1"}))


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXToggleSwitch.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_toggle_switch.css"
        assert css[0].is_file()

    def test_no_script_asset(self):
        assert PJXToggleSwitch.__pjx_descriptor__.js_paths == ()
