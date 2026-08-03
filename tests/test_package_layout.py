"""Guards the #539 package layout: v2 owns `pyjinhx`, v0.x is staged at `pyjinhx_v0`."""

import importlib
import subprocess
from pathlib import Path

import pytest

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
    """No tracked Python file may still import the v0.x tree as `pyjinhx.<v0 module>`.

    Only submodule names unique to the v0.x tree are checked here: several
    names (``assets``, ``config``, ``context``, ``registry``, ...) exist in
    both trees post-rename, so `pyjinhx.<name>` legitimately refers to the v2
    module by that point and can't be used as a v0.x signal.
    """
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
                    "cache",
                    "base",
                    "finder",
                    "keys",
                    "mutations",
                    "tags",
                    "utils",
                }:
                    offenders.append(f"{rel}: {stripped}")
    assert offenders == [], offenders


def test_pyjinhx_resolves_to_the_v2_rebuild():
    session = importlib.import_module("pyjinhx.session")
    assert hasattr(session, "RenderSession")
    segments = importlib.import_module("pyjinhx.segments")
    assert hasattr(segments, "RE_PASCAL_CASE_TAG_NAME")


def test_pyjinhx_is_not_the_v0_package():
    """v0-only surface must be absent from the v2 package."""
    mod = importlib.import_module("pyjinhx")
    assert not hasattr(mod, "Renderer")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("pyjinhx.renderer")


def test_no_tracked_file_mentions_pyjinhx2():
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    skip = {"CHANGELOG.md", "docs/superpowers/plans"}
    offenders = []
    for rel in tracked:
        if any(rel.startswith(s) for s in skip):
            continue
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "pyjinhx2" in text:
            offenders.append(rel)
    assert offenders == [], offenders
