"""Guards the #539 package layout: v2 owns `pyjinhx`, v0.x is staged at `pyjinhx_v0`."""

import importlib
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_v0_package_is_staged_under_pyjinhx_v0():
    mod = importlib.import_module("pyjinhx_v0")
    assert hasattr(mod, "Renderer")
    assert hasattr(mod, "Registry")
    assert mod.__file__ is not None
    assert Path(mod.__file__).parent.name == "pyjinhx_v0"


def test_v0_submodules_import_under_the_staged_name():
    renderer = importlib.import_module("pyjinhx_v0.renderer")
    assert hasattr(renderer, "Renderer")


def test_no_tracked_file_mentions_the_old_v0_import_root():
    """No tracked Python file may still import the v0.x tree as `pyjinhx.<v0 module>`."""
    tracked = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    offenders = []
    for rel in tracked:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import pyjinhx.", "from pyjinhx.")):
                module = stripped.split()[1]
                if module.split(".")[1] in {
                    "renderer",
                    "reactive",
                    "cache",
                    "assets",
                    "registry",
                    "base",
                    "config",
                }:
                    offenders.append(f"{rel}: {stripped}")
    assert offenders == [], offenders
