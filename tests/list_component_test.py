from tests.ui.button import Button
from tests.ui.button_list import ButtonList


def test_list_component():
    button1 = Button(id="btn-1", text="First Button")
    button2 = Button(id="btn-2", text="Second Button")
    button3 = Button(id="btn-3", text="Third Button")
    
    button_list = ButtonList(
        id="list-1",
        title="Action Buttons",
        buttons=[button1, button2, button3]
    )
    
    rendered = button_list.render()
    
    assert rendered == """<div id="list-1" class="button-list">
    <h3>Action Buttons</h3>
    <ul>
        
        <li><button id="btn-1">First Button</button></li>
        
        <li><button id="btn-2">Second Button</button></li>
        
        <li><button id="btn-3">Third Button</button></li>
        
    </ul>
</div>

<script>console.log('Button loaded');
console.log('Button loaded');
console.log('Button loaded');</script>"""

