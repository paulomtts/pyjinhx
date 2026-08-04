"""Regression guard for issue #739.

CPython auto-binds an imported submodule onto its parent package, so a module
named ``pyjinhx/component.py`` overwrites the lazily-exported callable
``pyjinhx.component``. These tests run in fresh interpreters because the
collision is only observable on a clean ``sys.modules``.
"""

import subprocess
import sys


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )


def test_from_pyjinhx_import_component_is_callable():
    result = _run(
        "from pyjinhx import component\n"
        "assert callable(component), f'component is not callable: {type(component)!r}'\n"
        "assert not isinstance(component, type(__import__('sys'))), 'component resolved to a module'\n"
    )
    assert result.returncode == 0, result.stderr


def test_pyjinhx_dot_component_is_callable():
    result = _run(
        "import pyjinhx\n"
        "assert callable(pyjinhx.component), f'component is not callable: {type(pyjinhx.component)!r}'\n"
        "assert not isinstance(pyjinhx.component, type(__import__('sys'))), 'component resolved to a module'\n"
    )
    assert result.returncode == 0, result.stderr


def test_no_component_submodule_exists():
    result = _run(
        "import importlib.util\n"
        "assert importlib.util.find_spec('pyjinhx.component') is None, "
        "'pyjinhx.component submodule still exists and will shadow the export'\n"
    )
    assert result.returncode == 0, result.stderr
