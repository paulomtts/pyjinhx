from tests.ui.button import Button
from tests.ui.panel import Panel


def test_dict_component():
    action_button = Button(id="action-btn", text="Click Me")
    
    panel = Panel(
        id="panel-1",
        title="My Panel",
        sections={
            "header": "Welcome",
            "action": action_button,
            "footer": "Thank you"
        }
    )
    
    rendered = panel.render()
    
    assert rendered == """<div id="panel-1" class="panel">
    <h2>My Panel</h2>
    <div class="panel-sections">
        
        <div class="section-header">
            
                <p>Welcome</p>
            
        </div>
        
        <div class="section-action">
            
                <button id="action-btn">Click Me</button>
            
        </div>
        
        <div class="section-footer">
            
                <p>Thank you</p>
            
        </div>
        
    </div>
</div>

<script>console.log('Button loaded');</script>"""

