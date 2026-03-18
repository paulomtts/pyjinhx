"""
Tests for lazy auto-import of co-located Python modules (Problem 2).

Prior to the fix, a BaseComponent subclass had to be explicitly imported at
startup for __init_subclass__ to fire and register the class.  Any tag whose
class was never imported fell back to a bare BaseComponent, losing type info
and co-located assets.

The fix: in _render_tag_node, when a tag name is not yet in the class registry,
_try_autodiscover_for_tag scans the template's directory for a co-located Python
module and imports it via importlib, triggering __init_subclass__ registration.
Deduplication prevents re-importing on subsequent renders.
"""
import os
import tempfile

import pytest
from jinja2 import Environment, FileSystemLoader

import pyjinhx.renderer as renderer_module
from pyjinhx import Registry
from pyjinhx.renderer import Renderer

# Python source written to temp files to define discoverable components.
_COMPONENT_SRC = """\
from pyjinhx import BaseComponent

class {class_name}(BaseComponent):
    id: str
    label: str = ""
"""


@pytest.fixture(autouse=True)
def reset_autodiscovery():
    """Clear the file-level dedup set before every test for isolation."""
    renderer_module._autodiscovered_files.clear()
    yield
    renderer_module._autodiscovered_files.clear()


def _drop_from_registry(class_name: str) -> None:
    """Remove a class from the class registry so autodiscovery can be re-tested."""
    Registry._class_registry.pop(class_name, None)


# ---------------------------------------------------------------------------
# Discovery search-order tests
# ---------------------------------------------------------------------------

def test_autodiscovery_snake_name_py():
    """Class in <snake_name>.py is auto-imported and registered."""
    Registry.clear_instances()
    class_name = "DiscoveredSnake"
    _drop_from_registry(class_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "discovered_snake.html"), "w") as f:
            f.write('<p id="{{ id }}">{{ label }}</p>\n')
        with open(os.path.join(temp_dir, "discovered_snake.py"), "w") as f:
            f.write(_COMPONENT_SRC.format(class_name=class_name))

        assert class_name not in Registry.get_classes()

        env = Environment(loader=FileSystemLoader(temp_dir))
        rendered = Renderer(env).render(f'<{class_name} id="s1" label="Hi"/>')

        assert '<p id="s1">Hi</p>' in rendered
        assert class_name in Registry.get_classes()


def test_autodiscovery_init_py_fallback():
    """Class in __init__.py is found when no snake_name.py exists."""
    Registry.clear_instances()
    class_name = "DiscoveredInit"
    _drop_from_registry(class_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "discovered_init.html"), "w") as f:
            f.write('<p id="{{ id }}">{{ label }}</p>\n')
        with open(os.path.join(temp_dir, "__init__.py"), "w") as f:
            f.write(_COMPONENT_SRC.format(class_name=class_name))

        assert class_name not in Registry.get_classes()

        env = Environment(loader=FileSystemLoader(temp_dir))
        rendered = Renderer(env).render(f'<{class_name} id="i1" label="World"/>')

        assert '<p id="i1">World</p>' in rendered
        assert class_name in Registry.get_classes()


def test_autodiscovery_any_py_last_resort():
    """Class in an arbitrarily named .py is found as a last resort."""
    Registry.clear_instances()
    class_name = "DiscoveredFallback"
    _drop_from_registry(class_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "discovered_fallback.html"), "w") as f:
            f.write('<p id="{{ id }}">{{ label }}</p>\n')
        with open(os.path.join(temp_dir, "components.py"), "w") as f:
            f.write(_COMPONENT_SRC.format(class_name=class_name))

        assert class_name not in Registry.get_classes()

        env = Environment(loader=FileSystemLoader(temp_dir))
        rendered = Renderer(env).render(f'<{class_name} id="f1" label="Fallback"/>')

        assert '<p id="f1">Fallback</p>' in rendered
        assert class_name in Registry.get_classes()


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------

def test_autodiscovery_file_imported_only_once():
    """A Python file is exec'd only once even when multiple tags trigger discovery."""
    Registry.clear_instances()
    class_name = "DiscoveredDedup"
    _drop_from_registry(class_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "discovered_dedup.html"), "w") as f:
            f.write('<span id="{{ id }}">{{ label }}</span>\n')
        py_path = os.path.join(temp_dir, "discovered_dedup.py")
        with open(py_path, "w") as f:
            f.write(_COMPONENT_SRC.format(class_name=class_name))

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env)

        renderer.render(f'<{class_name} id="d1" label="First"/>')
        renderer.render(f'<{class_name} id="d2" label="Second"/>')

        assert list(renderer_module._autodiscovered_files).count(py_path) == 1


def test_autodiscovery_skipped_when_already_registered():
    """No file is imported when the class is already in the class registry."""
    Registry.clear_instances()

    from pyjinhx import BaseComponent

    class AlreadyRegistered(BaseComponent):
        id: str
        label: str = ""

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "already_registered.html"), "w") as f:
            f.write('<div id="{{ id }}">{{ label }}</div>\n')
        py_path = os.path.join(temp_dir, "already_registered.py")
        with open(py_path, "w") as f:
            f.write("raise RuntimeError('should not be imported')\n")

        env = Environment(loader=FileSystemLoader(temp_dir))
        # Must not raise — the RuntimeError file must never be exec'd
        rendered = Renderer(env).render('<AlreadyRegistered id="r1" label="Safe"/>')

        assert '<div id="r1">Safe</div>' in rendered
        assert py_path not in renderer_module._autodiscovered_files


# ---------------------------------------------------------------------------
# Integration: autodiscovery + asset collection
# ---------------------------------------------------------------------------

def test_autodiscovered_class_collects_js():
    """After auto-import, the component's co-located JS is collected normally."""
    Registry.clear_instances()
    class_name = "DiscoveredWithJs"
    _drop_from_registry(class_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "discovered_with_js.html"), "w") as f:
            f.write('<button id="{{ id }}">{{ label }}</button>\n')
        with open(os.path.join(temp_dir, "discovered_with_js.py"), "w") as f:
            f.write(_COMPONENT_SRC.format(class_name=class_name))
        with open(os.path.join(temp_dir, "discovered-with-js.js"), "w") as f:
            f.write("console.log('auto-js loaded');")

        env = Environment(loader=FileSystemLoader(temp_dir))
        rendered = Renderer(env).render(f'<{class_name} id="j1" label="Click me"/>')

        assert '<button id="j1">Click me</button>' in rendered
        assert "console.log('auto-js loaded');" in rendered


def test_autodiscovered_class_collects_css():
    """After auto-import, the component's co-located CSS is collected normally."""
    Registry.clear_instances()
    class_name = "DiscoveredWithCss"
    _drop_from_registry(class_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "discovered_with_css.html"), "w") as f:
            f.write('<section id="{{ id }}">{{ label }}</section>\n')
        with open(os.path.join(temp_dir, "discovered_with_css.py"), "w") as f:
            f.write(_COMPONENT_SRC.format(class_name=class_name))
        with open(os.path.join(temp_dir, "discovered-with-css.css"), "w") as f:
            f.write("section { padding: 1rem; }")

        env = Environment(loader=FileSystemLoader(temp_dir))
        rendered = Renderer(env).render(f'<{class_name} id="c1" label="Content"/>')

        assert '<section id="c1">Content</section>' in rendered
        assert "section { padding: 1rem; }" in rendered
