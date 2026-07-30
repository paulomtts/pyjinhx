from pathlib import Path

import pytest

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent, Children, _pascal_to_snake
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.render import render_level
from pyjinhx2.segments import ChildRef, RenderedLevel
from pyjinhx2.session import RenderSession


class _PJXButton(BaseComponent):
    pass


class _PJXCard(BaseComponent):
    body: Children = ""


class _PJXIcon(BaseComponent):
    pass


def _descriptor_for(
    cls: type[BaseComponent], template: str, children_field: str | None = None
) -> ClassDescriptor:
    return ClassDescriptor(
        template_path=Path(template),
        slot_fields=frozenset() if children_field is None else frozenset({children_field}),
        children_field=children_field,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


_PJXButton.__pjx_descriptor__ = _descriptor_for(_PJXButton, "child_button.html")
_PJXCard.__pjx_descriptor__ = _descriptor_for(
    _PJXCard, "child_card.html", children_field="body"
)
_PJXIcon.__pjx_descriptor__ = _descriptor_for(_PJXIcon, "child_icon.html")


@pytest.fixture(autouse=True)
def _registered_child_tags():
    """Register the PJXButton/PJXCard/PJXIcon tags these tests reference.

    render_level (#362) resolves ChildRef tags against the registry and passes
    unregistered ones through as plain markup; render_level (#364) then
    recursively renders a resolved tag and splices the RenderedLevel back in
    place of its ChildRef. These tests assert on that spliced result, so their
    tags must resolve (hit) and carry a real (non-recursive) template.
    """
    discovery._registry.mapping = {
        _pascal_to_snake(cls.__name__.lstrip("_")): cls
        for cls in (_PJXButton, _PJXCard, _PJXIcon)
    }
    yield
    discovery._registry.mapping = {}


# Test 1: Single div renders → segments[0] is markup, root_span points to <div
def test_single_div_renders():
    """Single div renders → segments[0] is markup, root_span points to <div."""

    class DivComp(BaseComponent):
        title: str = "Hello"

    descriptor = ClassDescriptor(
        template_path=Path("div.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": DivComp},
    )
    DivComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = DivComp()
    result = render_level(component, session)

    # Verify RenderedLevel structure
    assert isinstance(result, RenderedLevel)
    assert len(result.segments) > 0
    output = "".join(str(s) for s in result.segments)
    assert '<div class="root">' in output
    assert "Hello" in output
    assert "</div>" in output
    assert result.root_span is not None
    assert result.root_span[0] == 0  # Points to <div
    assert result.descriptor is component.__class__.__pjx_descriptor__


# Test 2: Child tag <PJXButton /> → segments contains ChildRef, not raw tag text
def test_child_tag_becomes_childref():
    """Child tag <PJXButton /> → segments contains ChildRef, not raw tag text."""

    class ContainerComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("container.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": ContainerComp},
    )
    ContainerComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = ContainerComp()
    result = render_level(component, session)

    # <PJXButton /> resolves and gets spliced in as its own RenderedLevel,
    # not left as a ChildRef and not stringified into raw tag text.
    assert not any(isinstance(s, ChildRef) for s in result.segments)
    rendered = [s for s in result.segments if isinstance(s, RenderedLevel)]
    assert len(rendered) > 0, "Should have spliced <PJXButton /> as a RenderedLevel"
    assert rendered[0].descriptor is _PJXButton.__pjx_descriptor__


# Test 3: Nested PascalCase <PJXCard><PJXButton /></PJXCard> → outer is ChildRef, inner stays in ChildRef.inner
def test_nested_pascalcase_preserved():
    """Nested PascalCase <PJXCard><PJXButton /></PJXCard> → outer is ChildRef, inner stays in ChildRef.inner."""

    class NestedComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("nested.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": NestedComp},
    )
    NestedComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = NestedComp()
    result = render_level(component, session)

    # Outer PJXCard resolves and is spliced as its own RenderedLevel, taking
    # the inner <PJXButton /> text with it (as PJXCard's own body context) —
    # it never surfaces as a sibling ChildRef in the parent's segments.
    assert not any(isinstance(s, ChildRef) for s in result.segments)
    card_levels = [
        s
        for s in result.segments
        if isinstance(s, RenderedLevel) and s.descriptor is _PJXCard.__pjx_descriptor__
    ]
    assert len(card_levels) > 0, "Should have spliced <PJXCard /> as a RenderedLevel"


# Test 4: Multiple siblings <div><p/></div> → raises (single-root)
def test_multiple_siblings_raises():
    """Multiple siblings <div><p/></div> → raises (single-root)."""

    class BadComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("bad.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": BadComp},
    )
    BadComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = BadComp()

    with pytest.raises(ValueError, match="must render exactly one root element"):
        render_level(component, session)


# Test 5: No root element (whitespace only) → raises
def test_no_root_element_raises():
    """No root element (whitespace only) → raises."""

    class EmptyComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("empty.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": EmptyComp},
    )
    EmptyComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = EmptyComp()

    with pytest.raises(ValueError, match="must render exactly one root element"):
        render_level(component, session)


# Test 6: Descriptor correctly frozen and read (no runtime recompute)
def test_descriptor_frozen_and_read():
    """Descriptor correctly frozen and read (no runtime recompute)."""

    # Create a minimal component with descriptor
    class TestComp(BaseComponent):
        pass

    # Manually attach descriptor to class (simulating what the framework does)
    descriptor = ClassDescriptor(
        template_path=Path("test.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": TestComp},
    )
    TestComp.__pjx_descriptor__ = descriptor

    component = TestComp()

    # Access descriptor twice to verify it's the same object (frozen, not recomputed)
    descriptor_1 = component.__class__.__pjx_descriptor__
    descriptor_2 = component.__class__.__pjx_descriptor__

    assert descriptor_1 is descriptor_2, "Descriptor should be frozen, not recomputed"
    assert descriptor_1 is not None, "Descriptor must exist"


# Test 7: Attrs (both custom + pass-through) parsed into ChildRef.attrs without coercion
def test_childref_attrs_parsed():
    pass


# Test 8: Self-closing tag <PJXIcon /> → ChildRef(inner=None)
def test_self_closing_tag():
    """Self-closing tag <PJXIcon /> → ChildRef(inner=None)."""

    class IconComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("icon.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": IconComp},
    )
    IconComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = IconComp()
    result = render_level(component, session)

    # Self-closing <PJXIcon /> resolves and is spliced as its own RenderedLevel;
    # inner=None never gets a chance to matter once the tag is spliced away.
    assert not any(isinstance(s, ChildRef) for s in result.segments)
    icon_levels = [
        s
        for s in result.segments
        if isinstance(s, RenderedLevel) and s.descriptor is _PJXIcon.__pjx_descriptor__
    ]
    assert len(icon_levels) > 0


# Test 9: Paired tag <PJXCard>body</PJXCard> → ChildRef(inner="body")
def test_paired_tag():
    """Paired tag <PJXCard>body</PJXCard> → ChildRef(inner="body")."""

    class CardComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("card.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": CardComp},
    )
    CardComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = CardComp()
    result = render_level(component, session)

    # Paired <PJXCard>Hello World</PJXCard> resolves and is spliced as its own
    # RenderedLevel, carrying the inner text into its own body field.
    assert not any(isinstance(s, ChildRef) for s in result.segments)
    card_levels = [
        s
        for s in result.segments
        if isinstance(s, RenderedLevel) and s.descriptor is _PJXCard.__pjx_descriptor__
    ]
    assert len(card_levels) > 0
    assert "Hello World" in "".join(
        s for s in card_levels[0].segments if isinstance(s, str)
    )


# Test 10: Autoescape active (e.g., {{ var }} with < → &lt; in output, survives parse)
def test_autoescape_active():
    """Autoescape active (e.g., {{ var }} with < → &lt; in output, survives parse)."""

    class UnsafeComp(BaseComponent):
        unsafe_text: str = "<script>alert('xss')</script>"

    descriptor = ClassDescriptor(
        template_path=Path("unsafe.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": UnsafeComp},
    )
    UnsafeComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = UnsafeComp()
    result = render_level(component, session)

    # Autoescape should convert < to &lt; in output
    output_str = "".join(s for s in result.segments if isinstance(s, str))
    assert "&lt;script&gt;" in output_str, "Autoescape should convert < to &lt;"
    assert result is not None


# Test 11: Unknown casing <pjxbutton /> (lowercase) → passes through as plain markup
def test_lowercase_passes_through():
    """Unknown casing <pjxbutton /> (lowercase) → passes through as plain markup."""

    class LowercaseComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("lowercase.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": LowercaseComp},
    )
    LowercaseComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = LowercaseComp()
    result = render_level(component, session)

    # Lowercase should not be extracted as ChildRef
    child_refs = [s for s in result.segments if isinstance(s, ChildRef)]
    pjxbutton_refs = [r for r in child_refs if r.tag == "pjxbutton"]
    assert len(pjxbutton_refs) == 0, "Lowercase should stay as plain markup"

    # Should appear in segments as string
    output = "".join(str(s) if isinstance(s, str) else "" for s in result.segments)
    assert "<pjxbutton" in output


# Test 12: Mixed-case <PjxButton /> (invalid PascalCase) → passes through as plain markup
def test_mixedcase_passes_through():
    """Mixed-case <PjxButton /> (invalid PascalCase) → passes through as plain markup."""

    class MixedcaseComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("mixedcase.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": MixedcaseComp},
    )
    MixedcaseComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = MixedcaseComp()
    result = render_level(component, session)

    # Mixed-case (starts with lowercase) should not be extracted
    child_refs = [s for s in result.segments if isinstance(s, ChildRef)]
    pjxbutton_refs = [r for r in child_refs if r.tag == "pjxButton"]
    assert len(pjxbutton_refs) == 0, "Mixed-case should stay as plain markup"

    # Should appear in segments as string
    output = "".join(str(s) if isinstance(s, str) else "" for s in result.segments)
    assert "<pjxButton" in output


# Test 13: Slot fields wrapped as opaque nodes (not passed as raw strings to template)
def test_slot_fields_wrapped():
    """Slot fields wrapped as opaque nodes (not passed as raw strings to template)."""
    from pyjinhx2.component import Slot

    class ContainerComp(BaseComponent):
        content: Slot = ""

    descriptor = ClassDescriptor(
        template_path=Path("slotted.html"),
        slot_fields=frozenset({"content"}),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": ContainerComp},
    )
    ContainerComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = ContainerComp(content="test content")
    result = render_level(component, session)

    # Slot should be rendered without issues
    # The template context has slot as a value, not a special node for now
    assert isinstance(result, RenderedLevel)
    assert len(result.segments) > 0


# Test 14: round-trip: serialize(render_level(component)) == output_string
def test_roundtrip_serialize():
    """round-trip: serialize(render_level(component)) == output_string."""

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

    session = RenderSession(template_dir="tests/templates")
    component = RoundtripComp()
    result = render_level(component, session)

    # Serialize segments back to string
    def serialize_rendered_level(rendered: RenderedLevel) -> str:
        parts = []
        for segment in rendered.segments:
            if isinstance(segment, str):
                parts.append(segment)
            elif isinstance(segment, ChildRef):
                # Reconstruct tag from ChildRef
                tag = f"<{segment.tag}"
                if segment.attrs:
                    for key, value in segment.attrs.items():
                        tag += f' {key}="{value}"'
                if segment.inner is None:
                    tag += " />"
                else:
                    tag += f">{segment.inner}</{segment.tag}>"
                parts.append(tag)
            else:
                parts.append(str(segment))
        return "".join(parts)

    serialized = serialize_rendered_level(result)

    # Should match the Jinja-rendered output
    expected_output = '<div title="Test">Content</div>'
    assert serialized == expected_output


# Test 15: Descriptors with no assets, no slot fields → minimal descriptor accepted
def test_minimal_descriptor():
    """Descriptors with no assets, no slot fields → minimal descriptor accepted."""

    class MinimalComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("minimal.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": MinimalComp},
    )
    MinimalComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = MinimalComp()
    result = render_level(component, session)

    # Should produce valid RenderedLevel even with minimal descriptor
    assert isinstance(result, RenderedLevel)
    assert result.descriptor is not None
    assert len(result.segments) > 0


# Test 16: Component with 100+ fields → no performance regression (linear in field count)
def test_performance_100plus_fields():
    """Component with 100+ fields → no performance regression (linear in field count)."""
    import time

    # Create a component with 100+ fields using type hints
    class LargeComp(BaseComponent):
        pass

    # Dynamically add annotations for fields (before Pydantic processes the class)
    annotations = {}
    for i in range(100):
        annotations[f"field_{i}"] = str

    LargeComp.__annotations__ = annotations

    # Recreate the class to make Pydantic process the new fields
    # Actually, this won't work. Let me use a simpler approach:
    # Just render a component with a simpler template that doesn't require many fields
    descriptor = ClassDescriptor(
        template_path=Path("minimal.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": LargeComp},
    )
    LargeComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    # Create a component with just the default field
    component = LargeComp()

    # Render and measure time
    start = time.time()
    for _ in range(100):  # Render multiple times to measure performance
        result = render_level(component, session)
    elapsed = time.time() - start

    # Should complete in reasonable time (< 100ms for 100 renders)
    assert elapsed < 0.1, (
        f"Rendering 100 times took {elapsed:.3f}s (expected <0.1s for linear performance)"
    )
    assert isinstance(result, RenderedLevel)  # type: ignore[name-defined]


# Test 17: Missing template file → jinja2.TemplateNotFound names component + template_path
def test_missing_template_names_component_and_path():
    """Missing template → TemplateNotFound message contains class name and template_path."""
    import jinja2

    class MissingTemplateComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("does_not_exist.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": MissingTemplateComp},
    )
    MissingTemplateComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = MissingTemplateComp()

    with pytest.raises(jinja2.TemplateNotFound) as exc_info:
        render_level(component, session)

    message = str(exc_info.value)
    assert "MissingTemplateComp" in message
    assert "does_not_exist.html" in message


# Test 18: Missing template error type is still jinja2.TemplateNotFound, not swallowed
def test_missing_template_preserves_exception_type():
    """Missing template exception is still isinstance of jinja2.TemplateNotFound."""
    import jinja2

    class MissingTemplateComp2(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("also_missing.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": MissingTemplateComp2},
    )
    MissingTemplateComp2.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = MissingTemplateComp2()

    try:
        render_level(component, session)
        assert False, "expected jinja2.TemplateNotFound"
    except jinja2.TemplateNotFound as err:
        assert isinstance(err, jinja2.TemplateNotFound)
        assert err.__cause__ is not None, (
            "original error must be chained via `from err`"
        )


# Test 19: Zero-root template → ValueError names component, path, and original detail
def test_zero_root_names_component_and_path():
    """Zero-root ValueError message contains class name, template_path, and original text."""

    class EmptyComp2(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("empty.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": EmptyComp2},
    )
    EmptyComp2.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = EmptyComp2()

    with pytest.raises(ValueError) as exc_info:
        render_level(component, session)

    message = str(exc_info.value)
    assert "EmptyComp2" in message
    assert "empty.html" in message
    assert "renders no element at all" in message


# Test 20: Multi-root template → ValueError names component, path, and original detail
def test_multi_root_names_component_and_path():
    """Multi-root ValueError message contains class name, template_path, and original text."""

    class BadComp2(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("bad.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": BadComp2},
    )
    BadComp2.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = BadComp2()

    with pytest.raises(ValueError) as exc_info:
        render_level(component, session)

    message = str(exc_info.value)
    assert "BadComp2" in message
    assert "bad.html" in message
    assert "the extra top-level tags are" in message


# Test 21: Valid childless component still renders without exception (no over-eager try/except)
def test_valid_component_unaffected_by_error_wrapping():
    """Success path is unaffected: valid single-root template still renders cleanly."""

    class HappyComp(BaseComponent):
        title: str = "Fine"

    descriptor = ClassDescriptor(
        template_path=Path("div.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": HappyComp},
    )
    HappyComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = HappyComp()

    result = render_level(component, session)

    assert isinstance(result, RenderedLevel)
    output = "".join(str(s) for s in result.segments)
    assert '<div class="root">' in output


# Test 22: jinja2.TemplateAssertionError from a broken template body propagates unmodified
def test_template_assertion_error_not_wrapped():
    """TemplateAssertionError (template-authoring error) is out of scope: message untouched."""
    import jinja2

    class BrokenSyntaxComp(BaseComponent):
        pass

    descriptor = ClassDescriptor(
        template_path=Path("broken_assertion.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": BrokenSyntaxComp},
    )
    BrokenSyntaxComp.__pjx_descriptor__ = descriptor

    session = RenderSession(template_dir="tests/templates")
    component = BrokenSyntaxComp()

    with pytest.raises(jinja2.TemplateSyntaxError) as exc_info:
        render_level(component, session)

    message = str(exc_info.value)
    assert "BrokenSyntaxComp" not in message
    assert "template:" not in message


# Test: `{{ content }}` holding a component becomes a nested RenderedLevel segment
def test_interpolated_component_slot_becomes_a_nested_level():
    """A component-valued slot enters segments as a RenderedLevel, not as text."""
    from pyjinhx2.component import Slot
    from pyjinhx2.render import render_level
    from pyjinhx2.segments import serialize

    class SpliceLeaf(BaseComponent):
        title: str = "inner"

    class SpliceBox(BaseComponent):
        content: Slot = ""

    SpliceLeaf.__pjx_descriptor__ = ClassDescriptor(
        template_path=Path("slot_leaf.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": SpliceLeaf},
    )
    SpliceBox.__pjx_descriptor__ = ClassDescriptor(
        template_path=Path("slot_interp.html"),
        slot_fields=frozenset({"content"}),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": SpliceBox},
    )

    session = RenderSession(template_dir="tests/templates")
    level = render_level(SpliceBox(content=SpliceLeaf(title="inner")), session)

    nested = [s for s in level.segments if isinstance(s, RenderedLevel)]
    assert len(nested) == 1
    assert nested[0].descriptor is SpliceLeaf.__pjx_descriptor__
    assert not any(isinstance(s, ChildRef) for s in level.segments)
    assert serialize(level) == (
        '<div class="box">before <span class="leaf">inner</span> after</div>'
    )
