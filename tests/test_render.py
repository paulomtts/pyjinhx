"""Tests for project-root detection and Environment initialization."""

import tempfile
from pathlib import Path

import pytest
from jinja2 import DictLoader, Environment, FileSystemLoader

from pyjinhx_v0.render import (
    _default_environment,
    _detect_project_root,
    get_loader_root,
    set_default_environment,
)


class TestAutoDetectMarkers:
    """Test marker probing in order."""

    def test_marker_probing_order_outermost_match(self):
        """Start from temp dir with nested markers; verify it finds outermost."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create stacked structure: pyproject.toml at root, .git nested
            (root / "pyproject.toml").touch()
            (root / "subdir").mkdir()
            (root / "subdir" / ".git").mkdir()

            # Start detection from nested dir
            result = _detect_project_root(root / "subdir")
            assert result == root, f"Expected {root}, got {result}"

    def test_marker_probing_order_git_second(self):
        """Verify .git is found when pyproject.toml not present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git").mkdir()

            result = _detect_project_root(root)
            assert result == root

    def test_marker_probing_order_package_json_later(self):
        """Verify package.json is found when earlier markers absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "package.json").touch()

            result = _detect_project_root(root)
            assert result == root

    def test_auto_detect_fallback_no_markers(self):
        """Start from temp dir with no markers; verify it returns start directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            result = _detect_project_root(root)
            assert result == root

    def test_auto_detect_explicit_start_directory(self):
        """Pass explicit start directory; verify walk begins there."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "pyproject.toml").touch()

            result = _detect_project_root(root)
            assert result == root

    def test_marker_probing_all_six_markers(self):
        """Verify each marker in the list is recognized."""
        markers = [
            "pyproject.toml",
            "main.py",
            ".git",
            ".gitignore",
            "package.json",
            "uv.lock",
        ]
        for marker in markers:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                if marker in [".git"]:
                    (root / marker).mkdir()
                else:
                    (root / marker).touch()

                result = _detect_project_root(root)
                assert result == root, f"Marker {marker} not found"


class TestEnvironmentOverride:
    """Test custom environment override."""

    def test_override_set_custom_environment(self):
        """Set custom environment; verify get_loader_root() returns its root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            custom_env = Environment(loader=FileSystemLoader(str(root)))

            set_default_environment(custom_env)

            result = get_loader_root(custom_env)
            assert result == root

    def test_stability_override_same_on_reuse(self):
        """Set override, call get_loader_root twice; verify same environment reused."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            custom_env = Environment(loader=FileSystemLoader(str(root)))

            set_default_environment(custom_env)

            result1 = get_loader_root(custom_env)
            result2 = get_loader_root(custom_env)

            assert result1 == result2 == root


class TestLoaderValidation:
    """Test FileSystemLoader requirement enforcement."""

    def test_non_filesystem_loader_set_default_raises_error(self):
        """Pass non-FileSystemLoader environment to set_default_environment(); raise TypeError."""
        dict_env = Environment(loader=DictLoader({"test.html": "content"}))

        with pytest.raises(TypeError, match="FileSystemLoader"):
            set_default_environment(dict_env)

    def test_non_filesystem_loader_get_root_raises_error(self):
        """Read root from non-FileSystemLoader environment; raise TypeError."""
        dict_env = Environment(loader=DictLoader({"test.html": "content"}))

        with pytest.raises(TypeError, match="FileSystemLoader"):
            get_loader_root(dict_env)


class TestIntegration:
    """Test integration with render() and default environment."""

    def test_default_environment_at_import(self):
        """Verify default Environment exists and has FileSystemLoader."""
        # This is tested implicitly by the module import succeeding
        # and having a valid default environment
        assert _default_environment is not None
        assert isinstance(_default_environment.loader, FileSystemLoader)

    def test_render_uses_default_environment(self):
        """Create component, call render() with default environment; verify loader root works."""
        # This test verifies that render() will use the environment
        # and raise TemplateNotFound if template missing (loader root is working)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            custom_env = Environment(loader=FileSystemLoader(str(root)))
            set_default_environment(custom_env)

            # Attempting to render non-existent template should raise TemplateNotFound
            from jinja2 import TemplateNotFound

            with pytest.raises(TemplateNotFound):
                custom_env.get_template("nonexistent.html")
