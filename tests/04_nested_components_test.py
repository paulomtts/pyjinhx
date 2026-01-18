import pytest

from tests.ui.unified_component import UnifiedComponent


@pytest.mark.parametrize(
    ("html_files", "wrapper_id", "nested_id", "extra_html_suffix"),
    [
        ([], "wrapper-1", "action-btn-1", ""),
        (
            ["tests/ui/extra_content.html"],
            "wrapper-2",
            "action-btn-2",
            "<span>Extra HTML Content</span>",
        ),
    ],
)
def test_simple_nesting(
    html_files: list[str],
    wrapper_id: str,
    nested_id: str,
    extra_html_suffix: str,
):
    nested = UnifiedComponent(id=nested_id, text="Click Me")
    component = UnifiedComponent(
        id=wrapper_id,
        title="My Wrapper",
        nested=nested,
        html=html_files,
    )

    rendered = component._render()

    expected = (
        "<script>console.log('Button loaded');</script>\n"
        f'<div id="{wrapper_id}" class="test-component">\n'
        "    <h2>My Wrapper</h2>\n"
        '    <div class="nested">\n'
        f"        <p>Nested component ID: {nested_id}</p>\n"
        "        <p>Nested component text: Click Me</p>\n"
        f'        <div id="{nested_id}" class="test-component">\n'
        '    <div class="text">Click Me</div>\n'
        "</div>\n"
        "\n"
        f"    </div>{extra_html_suffix}\n</div>\n"
    )

    assert rendered == expected


def test_component_reuse():
    shared_component = UnifiedComponent(id="shared-1", text="Shared Component")

    component = UnifiedComponent(
        id="parent-1",
        title="Parent",
        items=[shared_component, shared_component, shared_component],
    )

    rendered = component.render()

    assert "shared-1" in str(rendered)
    assert str(rendered).count("shared-1") >= 3
    assert "Shared Component" in str(rendered)
