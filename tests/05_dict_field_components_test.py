from tests.ui.unified_component import UnifiedComponent


def test_dict_component():
    action_component = UnifiedComponent(id="action-btn", text="Click Me")
    
    component = UnifiedComponent(
        id="wrapper-1",
        title="My Wrapper",
        sections={
            "header": "Welcome",
            "action": action_component,
            "footer": "Thank you"
        }
    )
    
    rendered = component._render()
    
    assert rendered == """<script>console.log('Button loaded');</script>
<div id="wrapper-1" class="test-component">
    <h2>My Wrapper</h2>
    <div class="sections">
        
        <div class="section-header">
            Welcome
        </div>
        
        <div class="section-action">
            <div id="action-btn" class="test-component">
    <div class="text">Click Me</div>
</div>

        </div>
        
        <div class="section-footer">
            Thank you
        </div>
        
    </div>
</div>
"""

