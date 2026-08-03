"""L0.4.6 render — public API.

Tests the public render() wrapper: render_level() + serialize() behind a
single str-returning call, with a default RenderSession when none is passed.
"""

from pathlib import Path

import jinja2
import pytest

from pyjinhx.component import BaseComponent
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession, request_scope


def _make_component(template_path: str):
    """Build a childless component class wired to a template in tests/templates."""

    class DivComp(BaseComponent):
        title: str = "Hello"

    descriptor = ClassDescriptor(
        template_path=Path(template_path),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": DivComp},
    )
    DivComp.__pjx_descriptor__ = descriptor
    return DivComp


# Test 1: render(component) returns str, not RenderedLevel.
def test_render_returns_str(render_session):
    """render(component) returns str, not RenderedLevel."""
    DivComp = _make_component("div.html")
    component = DivComp()

    result = render(component, render_session)

    assert isinstance(result, str)


# Test 2: returned string round-trips the component's Jinja template output,
# including stamped root attrs, for a simple childless component.
def test_render_roundtrips_template_output(render_session):
    """Returned string matches the component's rendered markup exactly."""

    class RoundtripComp(BaseComponent):
        title: str = "Test"

    descriptor = ClassDescriptor(
        template_path=Path("roundtrip.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": RoundtripComp},
    )
    RoundtripComp.__pjx_descriptor__ = descriptor
    component = RoundtripComp()

    result = render(component, render_session)

    assert result == '<div title="Test">Content</div>'


# Test 3: render(component, session) with an explicit session uses that
# session's environment (custom template loader picked up).
def test_render_uses_explicit_session(tmp_path):
    """An explicit session's Jinja environment (custom template dir) is honored."""
    template_dir = tmp_path / "custom_templates"
    template_dir.mkdir()
    (template_dir / "custom.html").write_text('<div class="root">{{ title }}</div>')

    class CustomComp(BaseComponent):
        title: str = "Custom"

    descriptor = ClassDescriptor(
        template_path=Path("custom.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": CustomComp},
    )
    CustomComp.__pjx_descriptor__ = descriptor

    custom_session = RenderSession(template_dir=str(template_dir))
    component = CustomComp()

    result = render(component, custom_session)

    assert result == '<div class="root">Custom</div>'


# Test 4: render(component) without a session arg does not raise and
# produces valid output (default session construction works).
def test_render_without_session_uses_default(monkeypatch, tmp_path):
    """Omitting session constructs a default RenderSession() internally."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "default.html").write_text('<div class="root">{{ title }}</div>')
    monkeypatch.chdir(tmp_path)

    class DefaultComp(BaseComponent):
        title: str = "Default"

    descriptor = ClassDescriptor(
        template_path=Path("default.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": DefaultComp},
    )
    DefaultComp.__pjx_descriptor__ = descriptor
    component = DefaultComp()

    result = render(component)

    assert result == '<div class="root">Default</div>'


# Test 5: missing template raises jinja2.TemplateNotFound through the
# public API.
def test_render_missing_template_raises(render_session):
    """Missing template propagates jinja2.TemplateNotFound unchanged."""

    class MissingComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("does_not_exist.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": MissingComp},
    )
    MissingComp.__pjx_descriptor__ = descriptor
    component = MissingComp()

    with pytest.raises(jinja2.TemplateNotFound):
        render(component, render_session)


# Test 6: multi-root template raises ValueError through the public API.
def test_render_multiroot_raises(render_session):
    """Multi-root template propagates ValueError unchanged."""
    BadComp = _make_component("bad.html")
    component = BadComp()

    with pytest.raises(ValueError, match="must render exactly one root element"):
        render(component, render_session)


# Test 7: zero-root template raises ValueError through the public API.
def test_render_zeroroot_raises(render_session):
    """Zero-root (whitespace-only) template propagates ValueError unchanged."""
    EmptyComp = _make_component("empty.html")
    component = EmptyComp()

    with pytest.raises(ValueError, match="must render exactly one root element"):
        render(component, render_session)


# Test: component.render(session=...) delegates to the free render() with that
# exact session, ambient context or not.
def test_component_render_with_explicit_session(render_session):
    """component.render(session=s) matches render(component, s)."""
    DivComp = _make_component("div.html")

    assert DivComp().render(session=render_session) == render(DivComp(), render_session)


# Test: no-arg component.render() inside a request_scope picks the ambient
# session up off the ContextVar.
def test_component_render_uses_ambient_session(tmp_path):
    """Inside request_scope(), no-arg render() uses the scope's session."""
    template_dir = str(Path(__file__).parent.parent / "templates")
    DivComp = _make_component("div.html")

    with request_scope(template_dir=template_dir) as session:
        ambient = DivComp().render()

    assert ambient == render(DivComp(), RenderSession(template_dir=template_dir))
    assert ambient == render(DivComp(), session)


# Test: outside any request_scope, no-arg render() behaves exactly like passing
# session=None to the free function — a fresh default RenderSession, whose
# loader is the cwd-relative "templates" dir.
def test_component_render_without_session(monkeypatch):
    """Outside a scope, no-arg render() matches render(component, None)."""
    monkeypatch.chdir(Path(__file__).parent.parent)  # tests/, so "templates" resolves
    DivComp = _make_component("div.html")

    assert DivComp().render() == render(DivComp(), None)
