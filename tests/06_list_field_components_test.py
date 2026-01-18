from tests.ui.unified_component import UnifiedComponent


def test_nested_list_of_components():
    item1 = UnifiedComponent(id="btn-1", text="First Button")
    item2 = UnifiedComponent(id="btn-2", text="Second Button")
    item3 = UnifiedComponent(id="btn-3", text="Third Button")
    
    component = UnifiedComponent(
        id="list-1",
        title="Action Buttons",
        items=[item1, item2, item3]
    )
    
    rendered = component._render()
    
    assert rendered == """<script>console.log('Button loaded');</script>
<div id="list-1" class="test-component">
    <h2>Action Buttons</h2>
    <div class="items">
        <ul>
            
            <li><div id="btn-1" class="test-component">
    <div class="text">First Button</div>
</div>
</li>
            
            <li><div id="btn-2" class="test-component">
    <div class="text">Second Button</div>
</div>
</li>
            
            <li><div id="btn-3" class="test-component">
    <div class="text">Third Button</div>
</div>
</li>
            
        </ul>
    </div>
</div>
"""

