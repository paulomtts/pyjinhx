"""Make `.pjx` single-file components importable with no build step.

A `sys.meta_path` finder resolves a dotted name to a `<segment>.pjx` file on the
normal import search path (mirroring how `.py` is found), executes its
``{# python #}`` block as the module body, and binds the template body to the
component class. A `.py` shadowing a `.pjx` on the same path is a hard error.
"""
import importlib.abc
import importlib.machinery
import os
import sys
from typing import Sequence

from pyjinhx.sfc import split_pjx


def _search_paths(path: "Sequence[str] | None") -> "list[str]":
    return list(path) if path is not None else list(sys.path)


class PjxLoader(importlib.abc.Loader):
    def __init__(self, source_path: str) -> None:
        self._source_path = source_path

    def create_module(self, spec):  # default module creation
        return None

    def exec_module(self, module) -> None:
        with open(self._source_path, encoding="utf-8") as handle:
            source = handle.read()
        python_src, template_src = split_pjx(source)
        if python_src is None:
            raise ImportError(
                f"{self._source_path}: not a single-file component "
                f"(no {{# python #}} block)"
            )

        module.__file__ = self._source_path
        code = compile(python_src, self._source_path, "exec")
        exec(code, module.__dict__)

        component = self._select_component(module)
        component._pjx_inline_template = template_src
        component._pjx_source_path = self._source_path

    def _select_component(self, module):
        from pyjinhx.base import BaseComponent

        defined = [
            value
            for value in module.__dict__.values()
            if isinstance(value, type)
            and issubclass(value, BaseComponent)
            and value.__module__ == module.__name__
        ]
        if not defined:
            raise ImportError(
                f"{self._source_path}: no component class defined in the "
                f"{{# python #}} block"
            )
        if len(defined) > 1:
            names = ", ".join(sorted(cls.__name__ for cls in defined))
            raise ImportError(
                f"{self._source_path}: a .pjx must define exactly one component "
                f"class, but found {len(defined)} ({names}). Move the extras to "
                f"their own .pjx files."
            )
        return defined[0]


class PjxFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        segment = fullname.rpartition(".")[2]
        for entry in _search_paths(path):
            pjx_path = os.path.join(entry, f"{segment}.pjx")
            if not os.path.isfile(pjx_path):
                continue
            py_path = os.path.join(entry, f"{segment}.py")
            if os.path.isfile(py_path):
                raise ImportError(
                    f"{fullname}: both {segment}.py and {segment}.pjx exist in "
                    f"{entry!r}; remove one"
                )
            return importlib.machinery.ModuleSpec(
                fullname, PjxLoader(pjx_path), origin=pjx_path
            )
        return None


def install() -> None:
    """Insert the `.pjx` finder at the front of ``sys.meta_path`` (idempotent)."""
    if not any(isinstance(finder, PjxFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, PjxFinder())
