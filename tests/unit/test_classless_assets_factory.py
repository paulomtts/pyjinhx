"""
Tests for CSS/JS asset collection from classless components via the factory path.

Issue #122: component("Foo")(title="hi").render() did not collect co-located
CSS/JS assets.  The bug was that apply_component_render_assets checked
`type(component).__name__ == "BaseComponent"` to detect classless components,
but the component() factory path produces *named* subclasses (named after the
tag), so the guard never fired and assets were resolved against the wrong
directory via Finder.get_class_directory.

The fix adds a `_pjx_classless` ClassVar marker that is set on dynamically
built subclasses (bare classless / component() factory), and broadens the
guard to include it.
"""

import pytest

from pyjinhx import Renderer
from pyjinhx.base import component


@pytest.fixture(autouse=True)
def isolate_renderer(tmp_path):
    """Each test gets a fresh tmp_path environment; restore after."""
    Renderer.set_default_environment(str(tmp_path))
    yield tmp_path
    Renderer.set_default_environment(None)
    Renderer._default_renderers.clear()


# ---------------------------------------------------------------------------
# Factory path — bare classless (no-header) with co-located assets
# ---------------------------------------------------------------------------

def test_bare_classless_factory_css_collected(isolate_renderer):
    """CSS co-located with a bare (no-header) template IS inlined via factory path."""
    tmp_path = isolate_renderer
    comp_dir = tmp_path / "baz"
    comp_dir.mkdir()
    (comp_dir / "baz.html").write_text(
        "<span class='baz'>{{ content }}</span>",
        encoding="utf-8",
    )
    (comp_dir / "baz.css").write_text(".baz { font-size: 2em }", encoding="utf-8")

    Renderer.set_default_environment(str(tmp_path))
    html = str(component("Baz")(content="hello").render())

    assert ".baz { font-size: 2em }" in html, "CSS not inlined for bare classless factory path"


# ---------------------------------------------------------------------------
# Regression: file-backed class-based components still collect their assets
# ---------------------------------------------------------------------------

def test_class_based_builtin_still_collects_assets():
    """PJXButton (a real class-based builtin) still inlines its own CSS.

    This guards against the fix accidentally breaking class-based components.
    """
    from pyjinhx.builtins.ui.pjx_button.pjx_button import PJXButton

    html = str(PJXButton(label="Click me").render())

    # PJXButton's CSS contains its own selectors; just assert style is present
    assert "<style" in html, "PJXButton's CSS was not inlined (regression)"


# ---------------------------------------------------------------------------
# Marker check: _pjx_classless is set correctly
# ---------------------------------------------------------------------------

def test_pjx_classless_marker_set_on_bare_factory(isolate_renderer):
    """component() no-header fallback sets _pjx_classless = True."""
    tmp_path = isolate_renderer
    (tmp_path / "plain.html").write_text("<p>{{ text }}</p>", encoding="utf-8")
    Renderer.set_default_environment(str(tmp_path))

    Plain = component("Plain")
    assert getattr(Plain, "_pjx_classless", False) is True


def test_pjx_classless_marker_false_on_handwritten_class():
    """A hand-written BaseComponent subclass does NOT have _pjx_classless = True."""
    from pyjinhx.builtins.ui.pjx_button.pjx_button import PJXButton

    assert getattr(PJXButton, "_pjx_classless", False) is False
