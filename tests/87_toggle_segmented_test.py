# tests/87_toggle_segmented_test.py
"""Tests for ToggleSwitch and SegmentedControl builtins."""
import os
import re

from pyjinhx.builtins import SegmentedControl, ToggleSwitch


# ── ToggleSwitch ──────────────────────────────────────────────────────────────


def _toggle_root(html: str) -> str:
    match = re.search(r"<label[^>]*px-toggle-switch[^>]*>", html)
    assert match, html
    return match.group(0)


def test_toggle_switch_renders_checkbox():
    html = str(ToggleSwitch(id="ts1", name="active").render())
    assert 'type="checkbox"' in html
    assert 'name="active"' in html


def test_toggle_switch_value_attr():
    html = str(ToggleSwitch(id="ts2", name="n", value="yes").render())
    assert 'value="yes"' in html


def test_toggle_switch_checked_attr_when_true():
    html = str(ToggleSwitch(id="ts3", name="n", checked=True).render())
    assert " checked" in html


def test_toggle_switch_no_checked_attr_when_false():
    html = str(ToggleSwitch(id="ts4", name="n", checked=False).render())
    assert " checked" not in html


def test_toggle_switch_disabled_attr():
    html = str(ToggleSwitch(id="ts5", name="n", disabled=True).render())
    assert " disabled" in html


def test_toggle_switch_label_renders():
    html = str(ToggleSwitch(id="ts6", name="n", label="Dark mode").render())
    assert "Dark mode" in html
    assert "px-toggle-switch__label" in html


def test_toggle_switch_no_label_span_when_empty():
    html = str(ToggleSwitch(id="ts7", name="n", label="").render())
    markup = re.split(r"<style", html, maxsplit=1)[0]
    assert "px-toggle-switch__label" not in markup


def test_toggle_switch_track_and_thumb_present():
    html = str(ToggleSwitch(id="ts8", name="n").render())
    assert "px-toggle-switch__track" in html
    assert "px-toggle-switch__thumb" in html


def test_toggle_switch_no_js_file():
    """ToggleSwitch is CSS-only — no .js file should exist in the component folder."""
    import inspect
    from pyjinhx.builtins import ToggleSwitch as _TS
    component_dir = os.path.dirname(inspect.getfile(_TS))
    js_files = [f for f in os.listdir(component_dir) if f.endswith(".js")]
    assert js_files == [], f"Unexpected JS files in ToggleSwitch: {js_files}"


def test_toggle_switch_contract_fields():
    ts = ToggleSwitch(id="ts9", name="n")
    assert hasattr(ts, "class_name")
    assert hasattr(ts, "extra_attrs")


def test_toggle_switch_class_name_appended():
    html = str(ToggleSwitch(id="ts10", name="n", class_name="custom").render())
    root = _toggle_root(html)
    assert "custom" in root


# ── SegmentedControl ──────────────────────────────────────────────────────────


def _seg_root(html: str) -> str:
    match = re.search(r"<div[^>]*px-segmented-control[^>]*>", html)
    assert match, html
    return match.group(0)


def test_segmented_control_renders_radios():
    html = str(SegmentedControl(
        id="sc1", name="view",
        options=[("list", "List"), ("grid", "Grid")],
    ).render())
    assert html.count('type="radio"') == 2


def test_segmented_control_radio_names():
    html = str(SegmentedControl(
        id="sc2", name="mode",
        options=[("a", "A"), ("b", "B")],
    ).render())
    assert html.count('name="mode"') == 2


def test_segmented_control_selected_checked():
    html = str(SegmentedControl(
        id="sc3", name="view",
        options=[("list", "List"), ("grid", "Grid")],
        selected="list",
    ).render())
    # The "list" radio should be checked, grid should not
    assert 'value="list"' in html
    # The checked attr follows the value attr in the same input; check ordering
    list_pos = html.find('value="list"')
    grid_pos = html.find('value="grid"')
    checked_pos = html.find(' checked', list_pos)
    # checked appears after value="list" and before next input
    assert list_pos < checked_pos < grid_pos


def test_segmented_control_role_radiogroup():
    html = str(SegmentedControl(
        id="sc4", name="x",
        options=[("a", "A")],
    ).render())
    root = _seg_root(html)
    assert 'role="radiogroup"' in root


def test_segmented_control_disabled():
    html = str(SegmentedControl(
        id="sc5", name="x",
        options=[("a", "A"), ("b", "B")],
        disabled=True,
    ).render())
    assert html.count(" disabled") == 2


def test_segmented_control_json_string_coercion():
    sc = SegmentedControl(id="sc6", name="x", options='[["a", "A"], ["b", "B"]]')
    assert sc.options == [("a", "A"), ("b", "B")]


def test_segmented_control_text_labels():
    html = str(SegmentedControl(
        id="sc7", name="view",
        options=[("list", "List"), ("grid", "Grid")],
    ).render())
    assert "List" in html
    assert "Grid" in html
    assert "px-segmented-control__text" in html


def test_segmented_control_no_js_file():
    """SegmentedControl is CSS-only — no .js file should exist in the component folder."""
    import inspect
    from pyjinhx.builtins import SegmentedControl as _SC
    component_dir = os.path.dirname(inspect.getfile(_SC))
    js_files = [f for f in os.listdir(component_dir) if f.endswith(".js")]
    assert js_files == [], f"Unexpected JS files in SegmentedControl: {js_files}"


def test_segmented_control_contract_fields():
    sc = SegmentedControl(id="sc8", name="x")
    assert hasattr(sc, "class_name")
    assert hasattr(sc, "extra_attrs")


def test_segmented_control_class_name_appended():
    html = str(SegmentedControl(
        id="sc9", name="x",
        options=[("a", "A")],
        class_name="pill",
    ).render())
    root = _seg_root(html)
    assert "pill" in root
