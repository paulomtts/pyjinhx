# tests/unit/test_builtin_conventions.py
"""Mechanical enforcement of docs/guide/builtin-conventions.md."""
import os
import re

import pyjinhx.builtins as b

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
        assert "extra_attrs" in cls.model_fields, cls.__name__


def test_swept_templates_have_no_literal_aria_labels():
    for cls in SWEPT:
        directory = _component_dir(cls)
        for name in os.listdir(directory):
            if not name.endswith((".html", ".jinja")):
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
            assert "window.px = window.px || {}" in content, f"{cls.__name__}/{name}: missing px guard"


