import re

from pyjinhx import AssetMode, Renderer
from tests.ui.unified_component import UnifiedComponent


def _extract_scripts(rendered: str) -> list[str]:
    """Return a list of script block contents (inner text of each <script>...</script>)."""
    return re.findall(r"<script>(.*?)</script>", rendered, re.S)


def test_js_collection_order():
    component = UnifiedComponent(
        id="js-order-1", text="JS Order Test", js=["tests/ui/extra_script.js"]
    )

    rendered = str(component.render())
    scripts = _extract_scripts(rendered)

    # Both payloads must appear inside script blocks
    button_script = next((s for s in scripts if "console.log('Button loaded');" in s), None)
    extra_script = next((s for s in scripts if "console.log('Extra script loaded');" in s), None)
    assert button_script is not None, "Button JS payload not found inside any <script> block"
    assert extra_script is not None, "Extra JS payload not found inside any <script> block"

    # Auto JS (button) block must appear before the extra JS block in document order
    button_block_index = rendered.index(button_script)
    extra_block_index = rendered.index(extra_script)
    assert button_block_index < extra_block_index, "Auto JS block should come before extra JS block"


def test_js_collection_from_nested_components():
    nested1 = UnifiedComponent(id="nested-js-1", text="Nested 1")
    nested2 = UnifiedComponent(id="nested-js-2", text="Nested 2")

    component = UnifiedComponent(
        id="parent-js-1", title="Parent", items=[nested1, nested2]
    )

    rendered = str(component.render())
    scripts = _extract_scripts(rendered)

    # Deduplicated: exactly one script block contains the button payload
    matching = [s for s in scripts if "console.log('Button loaded');" in s]
    assert len(matching) == 1, (
        f"Expected exactly 1 script block with Button JS, found {len(matching)}"
    )


def test_js_collection_with_extra_js_in_nested():
    nested = UnifiedComponent(
        id="nested-extra-js-1",
        text="Nested with Extra JS",
        js=["tests/ui/extra_script.js"],
    )

    component = UnifiedComponent(
        id="parent-extra-js-1",
        title="Parent",
        nested=nested,
        js=["tests/ui/extra_script.js"],
    )

    rendered = str(component.render())
    scripts = _extract_scripts(rendered)

    assert any("console.log('Button loaded');" in s for s in scripts), (
        "Button JS payload not found inside any <script> block"
    )
    extra_matching = [s for s in scripts if "console.log('Extra script loaded');" in s]
    assert len(extra_matching) == 1, (
        f"Expected exactly 1 script block with Extra JS (deduplicated), found {len(extra_matching)}"
    )


def test_separate_script_tags():
    component = UnifiedComponent(
        id="sep-tags-1", text="Separate Tags", js=["tests/ui/extra_script.js"]
    )

    rendered = str(component.render())
    scripts = _extract_scripts(rendered)

    assert len(scripts) == 2, f"Expected 2 <script> blocks, found {len(scripts)}"


def test_inline_mode_regression():
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.INLINE,
        css_mode=AssetMode.INLINE,
    )
    rendered = str(
        UnifiedComponent(id="inline-1", text="Inline")._render(_renderer=renderer)
    )

    assert "<style>" in rendered
    assert ".test-component { color: red; }" in rendered
    assert "<script>console.log('Button loaded');</script>" in rendered
