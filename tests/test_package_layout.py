"""Guards the 1.0 package layout: `pyjinhx` is the v2 engine and v0.x is gone (#540)."""

import importlib
import inspect
import subprocess
import tomllib
from pathlib import Path

import pytest

import pyjinhx

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_EXPORTS = {
    # components & rendering
    "BaseComponent",
    "Slot",
    "Children",
    "component",
    "ReactiveComponent",
    "render",
    "RenderSession",
    # app wiring
    "setup",
    "PjxContext",
    # reactive authoring
    "mutates",
    "dirty",
    "MutationKey",
    "reactive_key",
    "PjxKey",
    "AppContext",
    # configuration
    "PjxSettings",
    "AssetMode",
}


def test_all_matches_expected_surface():
    assert set(pyjinhx.__all__) == EXPECTED_EXPORTS


def test_all_has_no_duplicates():
    assert len(pyjinhx.__all__) == len(set(pyjinhx.__all__))


def test_every_exported_name_is_importable():
    missing = [name for name in pyjinhx.__all__ if not hasattr(pyjinhx, name)]
    assert missing == []


def test_render_is_a_free_function_not_a_class():
    assert inspect.isfunction(pyjinhx.render)
    assert not inspect.isclass(pyjinhx.render)


def test_private_and_v1_symbols_are_not_exported():
    for name in ("OpenComponent", "Renderer", "Registry", "render_level"):
        assert name not in pyjinhx.__all__


def test_the_v0_package_is_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("pyjinhx_v0")
    assert not (REPO_ROOT / "pyjinhx_v0").exists()


def test_only_pyjinhx_is_packaged():
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert packages == ["pyjinhx"]


def test_no_tracked_file_mentions_the_v0_staging_package():
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    skip = {
        "CHANGELOG.md",
        "docs/migration.md",
        "docs/superpowers/",
        "tests/test_package_layout.py",
    }
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
        if "pyjinhx_v0" in text:
            offenders.append(rel)
    assert offenders == [], offenders


def test_no_tracked_file_mentions_the_old_v0_import_root():
    """Guards against ever reintroducing v0.x-shaped submodule names under `pyjinhx.*`.

    Only submodule names that were unique to the (now-deleted) v0.x tree are
    checked here — names like ``assets``, ``config``, ``context``,
    ``registry`` are legitimate v2 submodules and can't be used as a signal.
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
    skip = {"CHANGELOG.md", "docs/superpowers/plans", "tests/test_package_layout.py"}
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
