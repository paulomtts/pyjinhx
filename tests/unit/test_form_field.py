# tests/86_form_field_test.py
"""Tests for the PJXFormField builtin component."""
import re

from pyjinhx.builtins import PJXFormField


def _root(html: str) -> str:
    match = re.search(r"<div[^>]*pjx-form-field[^>]*>", html)
    assert match, html
    return match.group(0)


def test_form_field_label_renders():
    html = str(PJXFormField(id="ff1", label="Email").render())
    assert "Email" in html
    assert "pjx-form-field__label" in html


def test_form_field_for_wires_label_to_input():
    html = str(PJXFormField(id="ff2", label="Name", for_id="name-input").render())
    assert 'for="name-input"' in html


def test_form_field_no_for_when_empty():
    html = str(PJXFormField(id="ff3", label="Name").render())
    assert ' for=' not in html


def test_form_field_error_adds_modifier_class():
    html = str(PJXFormField(id="ff4", error="Required").render())
    root = _root(html)
    assert "pjx-form-field--error" in root


def test_form_field_error_renders_alert_paragraph():
    html = str(PJXFormField(id="ff5", error="Required").render())
    assert 'role="alert"' in html
    assert "pjx-form-field__error" in html
    assert "Required" in html


def test_form_field_error_has_stable_id():
    html = str(PJXFormField(id="ff6", error="Bad input").render())
    assert 'id="ff6-error"' in html


def test_form_field_error_replaces_help():
    html = str(PJXFormField(id="ff7", help="Enter your name", error="Required").render())
    # Strip inlined CSS/JS before negative assertions — class names appear in the stylesheet.
    markup = re.split(r"<style", html, maxsplit=1)[0]
    assert "pjx-form-field__error" in html
    assert "pjx-form-field__help" not in markup
    assert "Enter your name" not in markup


def test_form_field_help_shown_without_error():
    html = str(PJXFormField(id="ff8", help="We will never share your email").render())
    assert "pjx-form-field__help" in html
    assert "We will never share your email" in html
    assert 'id="ff8-help"' in html


def test_form_field_required_marker_present():
    html = str(PJXFormField(id="ff9", label="Email", required=True).render())
    assert "pjx-form-field__required" in html
    assert 'aria-hidden="true"' in html
    assert "*" in html


def test_form_field_no_required_marker_when_false():
    html = str(PJXFormField(id="ff10", label="Email", required=False).render())
    markup = re.split(r"<style", html, maxsplit=1)[0]
    assert "pjx-form-field__required" not in markup


def test_form_field_content_rendered():
    html = str(PJXFormField(id="ff11", content="<input id='my-in'>").render())
    assert "pjx-form-field__control" in html
    assert "<input" in html


def test_form_field_contract_fields():
    ff = PJXFormField(id="ff12")
    assert hasattr(ff, "class_name")
    assert hasattr(ff, "extra_attrs")


def test_form_field_no_error_class_when_no_error():
    html = str(PJXFormField(id="ff13", label="X").render())
    root = _root(html)
    assert "pjx-form-field--error" not in root


def test_form_field_class_name_appended():
    html = str(PJXFormField(id="ff14", class_name="my-field").render())
    root = _root(html)
    assert "my-field" in root


def test_form_field_extra_attrs_rendered():
    html = str(PJXFormField(id="ff15", extra_attrs={"data-test": "1"}).render())
    root = _root(html)
    assert 'data-test="1"' in root
