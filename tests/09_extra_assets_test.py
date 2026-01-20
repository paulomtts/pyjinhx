from tests.ui.unified_component import UnifiedComponent


def test_multiple_extra_js_files():
    component = UnifiedComponent(
        id="multi-js-1",
        text="Multiple JS",
        js=["tests/ui/extra_script.js", "tests/ui/extra_script.js"]
    )

    rendered = component.render()

    assert rendered == """<script>console.log('Button loaded');
console.log('Extra script loaded');

</script>
<div id="multi-js-1" class="test-component">
    <div class="text">Multiple JS</div>
</div>
"""
