from tests.ui.unified_component import UnifiedComponent


def test_mixed_list_content():
    item1 = UnifiedComponent(id="btn-1", text="First Button")
    item2 = UnifiedComponent(id="btn-2", text="Second Button")
    
    component = UnifiedComponent(
        id="mixed-list-1",
        title="Mixed List",
        items=["String Item 1", item1, "String Item 2", item2, "String Item 3"]
    )
    
    rendered = component.render()
    
    assert rendered == """<script>console.log('Button loaded');</script>
<div id="mixed-list-1" class="test-component">
    <h2>Mixed List</h2>
    <div class="items">
        <ul>
            
            <li>String Item 1</li>
            
            <li><div id="btn-1" class="test-component">
    <div class="text">First Button</div>
</div>
</li>
            
            <li>String Item 2</li>
            
            <li><div id="btn-2" class="test-component">
    <div class="text">Second Button</div>
</div>
</li>
            
            <li>String Item 3</li>
            
        </ul>
    </div>
</div>
"""


def test_mixed_dict_content():
    action_component = UnifiedComponent(id="action-btn", text="Click Me")
    footer_component = UnifiedComponent(id="footer-btn", text="Footer")
    
    component = UnifiedComponent(
        id="mixed-dict-1",
        title="Mixed Dict",
        sections={
            "header": "Welcome Text",
            "action": action_component,
            "middle": "Middle Text",
            "footer": footer_component,
            "end": "End Text"
        }
    )
    
    rendered = component.render()
    
    assert rendered == """<script>console.log('Button loaded');</script>
<div id="mixed-dict-1" class="test-component">
    <h2>Mixed Dict</h2>
    <div class="sections">
        
        <div class="section-header">
            Welcome Text
        </div>
        
        <div class="section-action">
            <div id="action-btn" class="test-component">
    <div class="text">Click Me</div>
</div>

        </div>
        
        <div class="section-middle">
            Middle Text
        </div>
        
        <div class="section-footer">
            <div id="footer-btn" class="test-component">
    <div class="text">Footer</div>
</div>

        </div>
        
        <div class="section-end">
            End Text
        </div>
        
    </div>
</div>
"""

