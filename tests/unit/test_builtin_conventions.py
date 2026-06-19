# tests/unit/test_builtin_conventions.py
"""Mechanical enforcement of docs/guide/builtin-conventions.md."""
import os
import re

import pyjinhx.builtins as b
from pyjinhx.base import _is_slot_field
from pyjinhx.utils import TEMPLATE_EXTENSIONS

SWEPT: list[type] = [getattr(b, name) for name in b.__all__]

UI_ROOT = os.path.join(os.path.dirname(b.__file__), "ui")


def _component_dir(cls: type) -> str:
    import inspect
    return os.path.dirname(inspect.getfile(cls))


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_swept_builtins_declare_contract_fields():
    for cls in SWEPT:
        assert "class_name" in cls.model_fields, cls.__name__


def test_swept_fields_holding_components_are_slots():
    # A builtin field whose annotation can hold a BaseComponent must be a slot —
    # either the component's children field or marked PjxSlot — so a raw-HTML
    # string renders the same (raw) as a passed component instead of being
    # autoescaped. Guards the #118 / PJXButton.center class of oversight.
    # (Fields that deliberately escape string items use list[Any], which does
    # not name BaseComponent and is intentionally exempt — e.g. PJXAvatarStack.)
    for cls in SWEPT:
        for name, field in cls.model_fields.items():
            if "BaseComponent" not in str(field.annotation):
                continue
            assert _is_slot_field(cls, name), (
                f"{cls.__name__}.{name}: annotation accepts a BaseComponent but the "
                f"field is not a slot (children field or PjxSlot) — a markup string "
                f"would be HTML-escaped. Declare it as Slot."
            )


def test_swept_templates_have_no_literal_aria_labels():
    for cls in SWEPT:
        directory = _component_dir(cls)
        for name in os.listdir(directory):
            if not name.endswith(TEMPLATE_EXTENSIONS):
                continue
            content = _read(os.path.join(directory, name))
            for match in re.finditer(r'aria-label="([^"]*)"', content):
                assert "{{" in match.group(1), (
                    f"{cls.__name__}/{name}: hardcoded aria-label {match.group(1)!r}; make it a prop"
                )


def test_swept_js_files_are_guarded_iifes():
    for cls in SWEPT:
        directory = _component_dir(cls)
        for name in os.listdir(directory):
            if not name.endswith(".js"):
                continue
            content = _read(os.path.join(directory, name)).lstrip()
            assert content.startswith("(function ()"), f"{cls.__name__}/{name}: not an IIFE"
            assert "window.pjx = window.pjx || {}" in content, f"{cls.__name__}/{name}: missing pjx guard"


