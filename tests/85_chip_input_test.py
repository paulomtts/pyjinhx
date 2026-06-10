# tests/85_chip_input_test.py
"""Tests for the ChipInput builtin component."""
import re

from pyjinhx.builtins import ChipInput


def _root(html: str) -> str:
    match = re.search(r"<div[^>]*px-chip-input[^>]*>", html)
    assert match, html
    return match.group(0)


def test_chip_input_renders_chips_for_each_value():
    html = str(ChipInput(id="ci1", name="tags", values=["alpha", "beta"]).render())
    # Each value should produce a hidden input
    hidden_inputs = re.findall(r'<input type="hidden" name="tags" value="([^"]+)"', html)
    assert hidden_inputs == ["alpha", "beta"], f"Expected ['alpha', 'beta'], got {hidden_inputs}"


def test_chip_input_hidden_inputs_have_correct_name():
    html = str(ChipInput(id="ci2", name="keywords", values=["foo", "bar", "baz"]).render())
    assert html.count('name="keywords"') >= 3  # text field + hidden inputs


def test_chip_input_renders_remove_buttons_when_enabled():
    html = str(ChipInput(id="ci3", name="tags", values=["x", "y"], remove_label="Remove chip").render())
    remove_buttons = re.findall(r'aria-label="([^"]+)"', html)
    # All should have the remove label
    assert all(label == "Remove chip" for label in remove_buttons), remove_buttons


def test_chip_input_disabled_no_text_field_no_remove_buttons():
    html = str(ChipInput(id="ci4", name="tags", values=["x"], disabled=True).render())
    assert 'type="text"' not in html, "Disabled chip input should have no text field"
    # Only check the structural markup — the JS source also contains the attribute name as a selector
    # so we narrow the search to the chip markup itself (before any <script> block).
    markup = re.split(r"<script", html, maxsplit=1)[0]
    assert 'data-px-chip-remove' not in markup, "Disabled chip input should have no remove buttons in markup"


def test_chip_input_disabled_hidden_inputs_still_present():
    html = str(ChipInput(id="ci5", name="tags", values=["x", "y"], disabled=True).render())
    hidden_inputs = re.findall(r'<input type="hidden" name="tags" value="([^"]+)"', html)
    assert hidden_inputs == ["x", "y"], "Hidden inputs must still be present when disabled"


def test_chip_input_data_name_attr_on_root():
    html = str(ChipInput(id="ci6", name="skills", values=[]).render())
    root = _root(html)
    assert 'data-name="skills"' in root


def test_chip_input_data_remove_label_on_root():
    html = str(ChipInput(id="ci7", name="tags", values=[], remove_label="Delete").render())
    root = _root(html)
    assert 'data-remove-label="Delete"' in root


def test_chip_input_data_disabled_attr_when_disabled():
    html = str(ChipInput(id="ci8", name="tags", values=[], disabled=True).render())
    root = _root(html)
    assert "data-disabled" in root


def test_chip_input_no_data_disabled_attr_when_enabled():
    html = str(ChipInput(id="ci9", name="tags", values=[]).render())
    root = _root(html)
    assert "data-disabled" not in root


def test_chip_input_contract_fields():
    ci = ChipInput(id="ci10", name="tags")
    assert hasattr(ci, "class_name")
    assert hasattr(ci, "extra_attrs")


def test_chip_input_class_name_appended():
    html = str(ChipInput(id="ci11", name="tags", class_name="my-class").render())
    root = _root(html)
    assert "my-class" in root


def test_chip_input_extra_attrs_rendered():
    html = str(ChipInput(id="ci12", name="tags", extra_attrs={"data-test": "yes"}).render())
    root = _root(html)
    assert 'data-test="yes"' in root


def test_chip_input_placeholder_in_text_field():
    html = str(ChipInput(id="ci13", name="tags", placeholder="Type here…").render())
    assert 'placeholder="Type here…"' in html


def test_chip_input_text_field_present_when_not_disabled():
    html = str(ChipInput(id="ci14", name="tags", values=[]).render())
    assert 'type="text"' in html


def test_chip_input_chip_value_order_preserved():
    values = ["c", "a", "b"]
    html = str(ChipInput(id="ci15", name="x", values=values).render())
    positions = [html.find(f'value="{v}"') for v in values]
    assert positions == sorted(positions), "Values should appear in order"
