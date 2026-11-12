"""PJXPasswordInput — v0.x field/markup parity on the v2 engine.

Port of tests/unit/test_password_input.py. v0.x's golden snapshot
(tests/unit/golden/password_input.html) does not carry over: v2 builtins assert
on rendered substrings, like every sibling port. The template composes no child
component tags — only div/input/button/span — so there is no child-tag render
coverage here and no registry fixture.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_password_input import PJXPasswordInput
from pyjinhx.client import read_pjx_theme_css
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


class TestFields:
    def test_defaults(self):
        field = PJXPasswordInput(id="p")
        assert field.name == "password"
        assert field.placeholder == ""
        assert field.autocomplete == "current-password"
        assert field.required is False
        assert field.show_label == "Show password"
        assert field.class_name == ""
        assert field.extra_attrs == {}

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXPasswordInput(id="p", bogus="x")  # type: ignore[call-arg]

    def test_inline_attr_kwargs_no_longer_pass_through(self):
        """v0.x accepted ``PJXPasswordInput(id="p", **{"data-test": "yes"})``.

        v2 core is strict (extra="forbid"), so a bare inline attr kwarg is now a
        ValidationError. The behavior it replaces is not dropped: pass-through
        moved to the declared ``extra_attrs`` mapping, covered by
        TestRender.test_extra_attrs_surface_on_the_root.
        """
        with pytest.raises(ValidationError):
            PJXPasswordInput(id="p", **{"data-test": "yes"})  # type: ignore[arg-type]


@pytest.fixture
def session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as the sibling builtin tests.
    """
    return RenderSession()


def _html(session, **kwargs) -> str:
    base = {"id": "p"}
    base.update(kwargs)
    return render(PJXPasswordInput(**base), session)  # type: ignore[arg-type]


class TestRender:
    def test_single_root_div(self, session):
        html = _html(session).strip()
        assert html.count("data-pjx-password ") + html.count("data-pjx-password>") == 1
        assert html.startswith('<div id="p"')
        assert html.endswith("</div>")

    def test_field_is_a_password_input(self, session):
        html = _html(session)
        assert '<input type="password"' in html
        assert 'id="p-field"' in html
        assert 'name="password"' in html

    def test_name_reaches_the_field(self, session):
        assert 'name="pwd1"' in _html(session, name="pwd1")

    def test_placeholder_only_renders_when_set(self, session):
        assert "placeholder=" not in _html(session)
        assert 'placeholder="Your password"' in _html(
            session, placeholder="Your password"
        )

    def test_autocomplete_renders_by_default_and_can_be_dropped(self, session):
        assert 'autocomplete="current-password"' in _html(session)
        assert "autocomplete=" not in _html(session, autocomplete="")

    def test_required_only_renders_when_true(self, session):
        assert " required" not in _html(session)
        assert " required" in _html(session, required=True)

    def test_toggle_button_markup_is_present(self, session):
        html = _html(session)
        assert "data-pjx-password-toggle" in html
        assert 'type="button"' in html
        assert 'class="pjx-password-input__eye"' in html

    def test_toggle_aria_label_comes_from_show_label(self, session):
        assert 'aria-label="Show password"' in _html(session)
        assert 'aria-label="Reveal"' in _html(session, show_label="Reveal")

    def test_toggle_defaults_to_unpressed(self, session):
        assert 'aria-pressed="false"' in _html(session)

    def test_class_name_is_appended_without_clobbering_base_classes(self, session):
        assert 'class="pjx-password-input my-pw"' in _html(session, class_name="my-pw")

    def test_empty_class_name_adds_nothing(self, session):
        assert 'class="pjx-password-input"' in _html(session)

    def test_extra_attrs_surface_on_the_root(self, session):
        html = _html(session, extra_attrs={"data-test": "yes"})
        assert 'data-test="yes"' in html[: html.index(">")]

    def test_user_supplied_values_are_escaped(self, session):
        html = _html(session, show_label="<script>x</script>", placeholder='"quoted"')
        assert "&lt;script&gt;x&lt;/script&gt;" in html
        assert "<script>" not in html
        assert "&#34;quoted&#34;" in html or "&quot;quoted&quot;" in html


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXPasswordInput.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_password_input.css"
        assert css[0].is_file()

    def test_script_is_frozen_on_the_descriptor(self):
        js = PJXPasswordInput.__pjx_descriptor__.js_paths
        assert len(js) == 1
        assert js[0].name == "pjx_password_input.js"
        assert js[0].is_file()


PASSWORD_CSS = PJXPasswordInput.__pjx_descriptor__.css_paths[0].read_text(
    encoding="utf-8"
)

PASSWORD_MARKUP = (
    '<div id="root" class="pjx-password-input">'
    '<input id="field" class="pjx-password-input__field" type="password">'
    '<button id="toggle" class="pjx-password-input__toggle" type="button">'
    '<span class="pjx-password-input__eye"></span></button>'
    "</div>"
)


def _password_style(page, element_id: str, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}'))"
        f".getPropertyValue('{prop}')"
    )


def test_password_input_defaults_use_light_fallbacks(page):
    page.set_content(
        f"<html><head><style>{PASSWORD_CSS}</style></head>"
        f"<body>{PASSWORD_MARKUP}</body></html>"
    )
    assert _password_style(page, "root", "border-top-color") == "rgb(228, 228, 231)"
    assert _password_style(page, "root", "border-top-left-radius") == "8px"
    assert _password_style(page, "root", "background-color") == "rgb(255, 255, 255)"
    assert _password_style(page, "field", "padding-top") == "8px"
    assert _password_style(page, "field", "padding-left") == "12px"
    # 2.75rem tracks the 2.5rem toggle, not the spacing scale.
    assert _password_style(page, "field", "padding-right") == "44px"
    assert _password_style(page, "field", "color") == "rgb(24, 24, 27)"
    assert _password_style(page, "toggle", "color") == "rgb(82, 82, 91)"
    assert _password_style(page, "toggle", "transition-duration") == "0.15s"


def test_password_input_focus_ring_uses_light_fallback(page):
    page.set_content(
        f"<html><head><style>{PASSWORD_CSS}</style></head>"
        f"<body>{PASSWORD_MARKUP}</body></html>"
    )
    page.focus("#field")
    assert _password_style(page, "root", "outline-style") == "solid"
    assert _password_style(page, "root", "outline-color") == "rgb(63, 63, 70)"


def test_password_input_component_token_still_wins(page):
    page.set_content(
        f"<html><head><style>{read_pjx_theme_css()}</style>"
        f"<style>{PASSWORD_CSS}</style>"
        "<style>:root { --pjx-password-input-border: rgb(1, 2, 3); }</style>"
        f"</head><body>{PASSWORD_MARKUP}</body></html>"
    )
    assert _password_style(page, "root", "border-top-color") == "rgb(1, 2, 3)"
