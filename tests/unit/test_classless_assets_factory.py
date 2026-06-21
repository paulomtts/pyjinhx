"""
Tests for CSS/JS asset collection from classless components via the factory path.

Issue #122: component("Foo")(title="hi").render() did not collect co-located
CSS/JS assets.  The bug was that apply_component_render_assets checked
`type(component).__name__ == "BaseComponent"` to detect classless components,
but both the {#def#}-header path and the component() factory path produce
*named* subclasses (named after the tag), so the guard never fired and assets
were resolved against the wrong directory via Finder.get_class_directory.

The fix adds a `_pjx_classless` ClassVar marker that is set on all dynamically
built subclasses, and broadens the guard to include it.
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
# Factory path — {#def#} header with co-located assets
# ---------------------------------------------------------------------------

def test_header_classless_factory_css_collected(isolate_renderer):
    """CSS co-located with a {#def#}-header template IS inlined via factory path."""
    tmp_path = isolate_renderer
    comp_dir = tmp_path / "foo"
    comp_dir.mkdir()
    (comp_dir / "foo.html").write_text(
        "{#def title: str #}\n<div class='foo'>{{ title }}</div>",
        encoding="utf-8",
    )
    (comp_dir / "foo.css").write_text(".foo { color: red }", encoding="utf-8")

    Renderer.set_default_environment(str(tmp_path))
    html = str(component("Foo")(title="hi").render())

    assert ".foo { color: red }" in html, "CSS was not inlined via factory path"


def test_header_classless_factory_js_collected(isolate_renderer):
    """JS co-located with a {#def#}-header template IS inlined via factory path."""
    tmp_path = isolate_renderer
    comp_dir = tmp_path / "bar"
    comp_dir.mkdir()
    (comp_dir / "bar.html").write_text(
        "{#def label: str #}\n<button>{{ label }}</button>",
        encoding="utf-8",
    )
    (comp_dir / "bar.js").write_text("console.log('bar');", encoding="utf-8")

    Renderer.set_default_environment(str(tmp_path))
    html = str(component("Bar")(label="click me").render())

    assert "console.log('bar');" in html, "JS was not inlined via factory path"


def test_header_classless_factory_both_assets_collected(isolate_renderer):
    """Both CSS and JS are inlined for a {#def#}-header component via factory."""
    tmp_path = isolate_renderer
    comp_dir = tmp_path / "gadget"
    comp_dir.mkdir()
    (comp_dir / "gadget.html").write_text(
        "{#def title: str #}\n<div class='gadget'>{{ title }}</div>",
        encoding="utf-8",
    )
    (comp_dir / "gadget.css").write_text(".gadget { margin: 0 }", encoding="utf-8")
    (comp_dir / "gadget.js").write_text("console.log('gadget');", encoding="utf-8")

    Renderer.set_default_environment(str(tmp_path))
    html = str(component("Gadget")(title="test").render())

    assert ".gadget { margin: 0 }" in html, "CSS not inlined"
    assert "console.log('gadget');" in html, "JS not inlined"


# ---------------------------------------------------------------------------
# Factory path — no {#def#} header (bare classless) with co-located assets
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
# Tag path — {#def#} header with co-located assets
# ---------------------------------------------------------------------------

def test_header_classless_tag_css_collected(isolate_renderer):
    """CSS co-located with a {#def#}-header template IS inlined via tag path."""
    tmp_path = isolate_renderer
    comp_dir = tmp_path / "greet"
    comp_dir.mkdir()
    (comp_dir / "greet.html").write_text(
        "{#def name: str #}\n<h1 class='greet'>Hello {{ name }}</h1>",
        encoding="utf-8",
    )
    (comp_dir / "greet.css").write_text(".greet { color: green }", encoding="utf-8")

    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()
    html = renderer.render('<Greet name="world"/>')

    assert ".greet { color: green }" in html, "CSS not inlined via tag path"


def test_header_classless_tag_js_collected(isolate_renderer):
    """JS co-located with a {#def#}-header template IS inlined via tag path."""
    tmp_path = isolate_renderer
    comp_dir = tmp_path / "alert"
    comp_dir.mkdir()
    (comp_dir / "alert.html").write_text(
        "{#def msg: str #}\n<div class='alert'>{{ msg }}</div>",
        encoding="utf-8",
    )
    (comp_dir / "alert.js").write_text("console.log('alert');", encoding="utf-8")

    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()
    html = renderer.render('<Alert msg="watch out"/>')

    assert "console.log('alert');" in html, "JS not inlined via tag path"


# ---------------------------------------------------------------------------
# Regression: file-backed class-based components still collect their assets
# ---------------------------------------------------------------------------

def test_class_based_builtin_still_collects_assets():
    """PJXButton (a real class-based builtin) still inlines its own CSS.

    This guards against the fix accidentally breaking class-based components.
    """
    from pyjinhx.builtins.ui.pjx_button.pjx_button import PJXButton

    html = str(PJXButton(content="Click me").render())

    # PJXButton's CSS contains its own selectors; just assert style is present
    assert "<style" in html, "PJXButton's CSS was not inlined (regression)"


# ---------------------------------------------------------------------------
# Marker check: _pjx_classless is set correctly
# ---------------------------------------------------------------------------

def test_pjx_classless_marker_set_on_header_model(isolate_renderer):
    """{#def#} header path sets _pjx_classless = True on the dynamic subclass."""
    tmp_path = isolate_renderer
    (tmp_path / "mycomp.html").write_text(
        "{#def title: str #}\n<div>{{ title }}</div>",
        encoding="utf-8",
    )
    Renderer.set_default_environment(str(tmp_path))

    MyComp = component("Mycomp")
    assert getattr(MyComp, "_pjx_classless", False) is True


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
