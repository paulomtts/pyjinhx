# tests/88_password_input_test.py
"""Tests for the PasswordInput builtin component."""
import re

from pyjinhx.builtins import PasswordInput


def _root(html: str) -> str:
    match = re.search(r"<div[^>]*px-password-input[^>]*>", html)
    assert match, html
    return match.group(0)


def test_password_input_renders_password_field():
    html = str(PasswordInput(id="pi1").render())
    assert 'type="password"' in html


def test_password_input_field_id():
    html = str(PasswordInput(id="pi2").render())
    assert 'id="pi2-field"' in html


def test_password_input_field_name_default():
    html = str(PasswordInput(id="pi3").render())
    assert 'name="password"' in html


def test_password_input_field_name_custom():
    html = str(PasswordInput(id="pi4", name="current_password").render())
    assert 'name="current_password"' in html


def test_password_input_autocomplete_default():
    html = str(PasswordInput(id="pi5").render())
    assert 'autocomplete="current-password"' in html


def test_password_input_autocomplete_custom():
    html = str(PasswordInput(id="pi6", autocomplete="new-password").render())
    assert 'autocomplete="new-password"' in html


def test_password_input_required_attr():
    html = str(PasswordInput(id="pi7", required=True).render())
    assert " required" in html


def test_password_input_no_required_when_false():
    html = str(PasswordInput(id="pi8", required=False).render())
    assert " required" not in html


def test_password_input_placeholder():
    html = str(PasswordInput(id="pi9", placeholder="Enter password").render())
    assert 'placeholder="Enter password"' in html


def test_password_input_toggle_button_present():
    html = str(PasswordInput(id="pi10").render())
    assert 'data-px-password-toggle' in html
    assert 'type="button"' in html


def test_password_input_toggle_aria_label_show():
    html = str(PasswordInput(id="pi11", show_label="Show").render())
    assert 'aria-label="Show"' in html


def test_password_input_toggle_aria_pressed_false():
    html = str(PasswordInput(id="pi12").render())
    assert 'aria-pressed="false"' in html



def test_password_input_data_px_password_on_root():
    html = str(PasswordInput(id="pi14").render())
    root = _root(html)
    assert "data-px-password" in root


def test_password_input_contract_fields():
    pi = PasswordInput(id="pi15")
    assert hasattr(pi, "class_name")
    assert hasattr(pi, "extra_attrs")


def test_password_input_class_name_appended():
    html = str(PasswordInput(id="pi16", class_name="custom").render())
    root = _root(html)
    assert "custom" in root


def test_password_input_extra_attrs_rendered():
    html = str(PasswordInput(id="pi17", extra_attrs={"data-test": "ok"}).render())
    root = _root(html)
    assert 'data-test="ok"' in root
