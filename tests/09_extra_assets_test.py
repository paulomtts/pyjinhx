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


def test_multiple_extra_html_files():
    component = UnifiedComponent(
        id="multi-html-1",
        text="Multiple HTML",
        html=["tests/ui/extra_content.html", "tests/ui/extra_content.html"]
    )
    
    rendered = component.render()
    
    assert rendered == """<script>console.log('Button loaded');</script>
<div id="multi-html-1" class="test-component">
    <div class="text">Multiple HTML</div><span>Extra HTML Content</span>
</div>
"""


def test_multiple_extra_js_and_html():
    component = UnifiedComponent(
        id="multi-files-1",
        text="Multiple Files",
        js=["tests/ui/extra_script.js"],
        html=["tests/ui/extra_content.html"]
    )
    
    rendered = component.render()
    
    assert rendered == """<script>console.log('Button loaded');
console.log('Extra script loaded');

</script>
<div id="multi-files-1" class="test-component">
    <div class="text">Multiple Files</div><span>Extra HTML Content</span>
</div>
"""

