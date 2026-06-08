from __future__ import annotations

import importlib.util
import logging
import os
import sys
from typing import ClassVar

from ..utils import pascal_case_to_snake_case

logger = logging.getLogger("pyjinhx")


class ComponentAutodiscover:
    """Import co-located Python modules to register ``BaseComponent`` subclasses."""

    _imported_files: ClassVar[set[str]] = set()

    @classmethod
    def clear(cls) -> None:
        """Drop the deduplication set. Mainly for tests."""
        cls._imported_files.clear()

    @classmethod
    def import_from_file(cls, filepath: str) -> None:
        """Import a Python file by path to trigger ``BaseComponent`` registration."""
        if filepath in cls._imported_files:
            return
        cls._imported_files.add(filepath)
        try:
            module_name = (
                f"_pyjinhx_autodiscovered_{os.path.splitext(os.path.basename(filepath))[0]}"
            )
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                return
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = (
                module  # required for inspect.getfile to resolve the class
            )
            spec.loader.exec_module(module)
        except Exception:
            logger.debug("Failed to autodiscover module at %s", filepath, exc_info=True)

    @classmethod
    def try_for_tag(cls, tag_name: str, template_path: str | None) -> None:
        """
        Look for a co-located Python module next to the template and import it.

        Search order: ``<snake_name>.py`` → ``__init__.py`` → first alphabetical ``.py``.
        """
        if template_path is None:
            return
        component_dir = os.path.dirname(template_path)
        snake_name = pascal_case_to_snake_case(tag_name)
        for filename in (f"{snake_name}.py", "__init__.py"):
            candidate = os.path.join(component_dir, filename)
            if os.path.exists(candidate):
                cls.import_from_file(candidate)
                return
        try:
            py_files = sorted(f for f in os.listdir(component_dir) if f.endswith(".py"))
            if py_files:
                cls.import_from_file(os.path.join(component_dir, py_files[0]))
        except OSError:
            pass
