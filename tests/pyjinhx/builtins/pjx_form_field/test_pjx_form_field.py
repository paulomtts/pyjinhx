"""PJXFormField — v0.x field/markup parity on the v2 engine.

Port of tests/unit/test_form_field.py. v0.x's golden snapshot
(tests/unit/golden/form_field.html) does not carry over: v2 builtins assert on
rendered substrings, like every sibling port. The template composes no child
component tags, so ``content`` is exercised as a plain Slot — a string leg and
a nested-component leg — with no registry fixture, unlike PJXButton's
region-loader leg.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_form_field import PJXFormField


class TestFields:
    def test_defaults(self):
        field = PJXFormField(id="ff")
        assert field.label == ""
        assert field.for_id == ""
        assert field.content == ""
        assert field.help == ""
        assert field.error == ""
        assert field.required is False
        assert field.class_name == ""
        assert field.extra_attrs == {}

    def test_content_is_a_declared_slot_field(self):
        assert "content" in PJXFormField.__pjx_descriptor__.slot_fields

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXFormField(id="ff", bogus="x")  # type: ignore[call-arg]

    def test_inline_attr_kwargs_no_longer_pass_through(self):
        """v0.x accepted ``PJXFormField(id="ff", **{"data-test": "1"})``.

        v2 core is strict (extra="forbid"), so a bare inline attr kwarg is now a
        ValidationError. The behavior it replaces is not dropped: pass-through
        moved to the declared ``extra_attrs`` mapping, covered by
        TestRender.test_extra_attrs_surface_on_the_root.
        """
        with pytest.raises(ValidationError):
            PJXFormField(id="ff", **{"data-test": "1"})  # type: ignore[arg-type]


from pyjinhx.builtins.ui.pjx_spinner import PJXSpinner
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as the sibling builtin tests.
    """
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "ff"}
    base.update(kwargs)
    return render(PJXFormField(**base), session)  # type: ignore[arg-type]


def _root(html: str) -> str:
    return html[: html.index(">")]


class TestRender:
    def test_single_root_div(self, session):
        html = _html(session, label="Email").strip()
        assert html.startswith('<div id="ff"')
        assert html.endswith("</div>")
        assert html.count("pjx-form-field__control") == 1

    def test_label_renders_when_set(self, session):
        html = _html(session, label="Email")
        assert "pjx-form-field__label" in html
        assert ">Email" in html

    def test_no_label_element_when_label_is_empty(self, session):
        assert "pjx-form-field__label" not in _html(session)

    def test_for_id_wires_the_label_to_the_control(self, session):
        assert 'for="name-input"' in _html(session, label="Name", for_id="name-input")

    def test_no_for_attribute_when_for_id_is_empty(self, session):
        assert " for=" not in _html(session, label="Name")

    def test_error_adds_the_modifier_class_to_the_root(self, session):
        assert "pjx-form-field--error" in _root(_html(session, error="Required"))

    def test_no_error_modifier_class_without_an_error(self, session):
        assert "pjx-form-field--error" not in _root(_html(session, label="X"))

    def test_error_renders_an_alert_paragraph_with_a_stable_id(self, session):
        html = _html(session, error="Bad input")
        assert 'role="alert"' in html
        assert "pjx-form-field__error" in html
        assert 'id="ff-error"' in html
        assert "Bad input" in html

    def test_error_suppresses_help_entirely(self, session):
        html = _html(session, help="Enter your name", error="Required")
        assert "pjx-form-field__error" in html
        assert "pjx-form-field__help" not in html
        assert "Enter your name" not in html

    def test_help_renders_without_an_error(self, session):
        html = _html(session, help="We never share your email")
        assert "pjx-form-field__help" in html
        assert 'id="ff-help"' in html
        assert "We never share your email" in html

    def test_required_marker_renders_with_a_label(self, session):
        html = _html(session, label="Email", required=True)
        assert "pjx-form-field__required" in html
        assert 'aria-hidden="true"' in html
        assert "*" in html

    def test_no_required_marker_when_not_required(self, session):
        assert "pjx-form-field__required" not in _html(session, label="Email")

    def test_no_required_marker_without_a_label(self, session):
        assert "pjx-form-field__required" not in _html(session, required=True)

    def test_string_content_lands_in_the_control_wrapper_escaped(self, session):
        html = _html(session, content="<script>x</script>")
        control = html[html.index("pjx-form-field__control") :]
        assert "&lt;script&gt;x&lt;/script&gt;" in control
        assert "<script>" not in html

    def test_component_content_renders_inside_the_control_wrapper(self, session):
        html = _html(session, content=PJXSpinner(id="ff-spin"))
        start = html.index("pjx-form-field__control")
        assert html.index('id="ff-spin"', start) > start
        assert "pjx-spinner" in html[start:]

    def test_class_name_is_appended_without_clobbering_base_classes(self, session):
        assert 'class="pjx-form-field my-field"' in _html(
            session, class_name="my-field"
        )

    def test_empty_class_name_adds_nothing(self, session):
        assert 'class="pjx-form-field"' in _html(session)

    def test_extra_attrs_surface_on_the_root(self, session):
        assert 'data-test="1"' in _root(_html(session, extra_attrs={"data-test": "1"}))


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXFormField.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_form_field.css"
        assert css[0].is_file()

    def test_no_script_asset(self):
        assert PJXFormField.__pjx_descriptor__.js_paths == ()
