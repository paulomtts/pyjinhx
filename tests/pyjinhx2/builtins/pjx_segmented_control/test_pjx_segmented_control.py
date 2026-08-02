"""PJXSegmentedControl — v0.x field/markup parity on the v2 engine.

Partial port of tests/unit/test_toggle_segmented.py: only the
``test_segmented_control_*`` cases carry over here. The PJXToggleSwitch cases in
that same file belong to #514. v0.x's golden-snapshot comparison does not carry
over either — v2 builtins assert on rendered substrings, like every sibling
port.
"""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.ui.pjx_segmented_control import PJXSegmentedControl
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession

OPTIONS = [("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")]


@pytest.fixture
def session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as the sibling builtin tests.
    """
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "sc", "name": "plan", "options": OPTIONS}
    base.update(kwargs)
    return render(PJXSegmentedControl(**base), session)  # type: ignore[arg-type]


def _root(html: str) -> str:
    return html[: html.index(">")]


class TestFields:
    def test_defaults(self):
        control = PJXSegmentedControl(id="sc", name="plan")
        assert control.name == "plan"
        assert control.options == []
        assert control.selected == ""
        assert control.disabled is False
        assert control.class_name == ""
        assert control.extra_attrs == {}

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXSegmentedControl(id="sc", name="plan", bogus="x")  # type: ignore[call-arg]

    def test_inline_attr_kwargs_no_longer_pass_through(self):
        """v0.x accepted ``PJXSegmentedControl(..., **{"data-test": "1"})``.

        v2 core is strict (extra="forbid"), so a bare inline attr kwarg is now a
        ValidationError. The behavior it replaces is not dropped: pass-through
        moved to the declared ``extra_attrs`` mapping, covered by
        TestRender.test_extra_attrs_surface_on_the_root.
        """
        with pytest.raises(ValidationError):
            PJXSegmentedControl(id="sc", name="plan", **{"data-test": "1"})  # type: ignore[arg-type]

    def test_json_string_options_coercion(self):
        control = PJXSegmentedControl(
            id="sc",
            name="plan",
            options='[["a","A"],["b","B"]]',  # type: ignore[arg-type]
        )
        assert control.options == [("a", "A"), ("b", "B")]


class TestRender:
    def test_single_root_div(self, session):
        html = _html(session).strip()
        assert html.startswith('<div id="sc"')
        assert html.endswith("</div>")
        assert 'role="radiogroup"' in _root(html)

    def test_renders_one_segment_per_option(self, session):
        html = _html(session)
        assert html.count("pjx-segmented-control__segment") == 3
        assert html.count('type="radio"') == 3

    def test_radio_name_matches_field_name(self, session):
        assert _html(session).count('name="plan"') == 3

    def test_selected_option_is_checked(self, session):
        html = _html(session, selected="b")
        assert html.count(" checked") == 1
        assert 'value="b" checked' in html

    def test_no_option_checked_when_selected_is_empty_or_unmatched(self, session):
        assert " checked" not in _html(session)
        assert " checked" not in _html(session, selected="zzz")

    def test_disabled_adds_disabled_to_every_input(self, session):
        assert _html(session, disabled=True).count(" disabled") == 3

    def test_not_disabled_by_default(self, session):
        assert " disabled" not in _html(session)

    def test_text_labels_render_in_span(self, session):
        html = _html(session)
        assert html.count("pjx-segmented-control__text") == 3
        assert ">Alpha</span>" in html

    def test_label_text_renders_escaped(self, session):
        html = _html(session, options=[("x", "<script>x</script>")])
        assert "&lt;script&gt;x&lt;/script&gt;" in html
        assert "<script>" not in html

    def test_class_name_is_appended_without_clobbering_base_classes(self, session):
        assert 'class="pjx-segmented-control my-sc"' in _html(
            session, class_name="my-sc"
        )

    def test_empty_class_name_adds_nothing(self, session):
        assert 'class="pjx-segmented-control"' in _html(session)

    def test_extra_attrs_surface_on_the_root(self, session):
        assert 'data-test="1"' in _root(_html(session, extra_attrs={"data-test": "1"}))


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXSegmentedControl.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_segmented_control.css"
        assert css[0].is_file()

    def test_no_script_asset(self):
        assert PJXSegmentedControl.__pjx_descriptor__.js_paths == ()
