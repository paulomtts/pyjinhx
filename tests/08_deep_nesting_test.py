from tests.ui.unified_component import UnifiedComponent


def test_3_level_deep_nesting():
    level3 = UnifiedComponent(id="level3-1", text="Level 3 Message")
    level2 = UnifiedComponent(id="level2-1", title="Level 2", nested=level3)
    level1 = UnifiedComponent(id="level1-1", title="Level 1", nested=level2)
    
    rendered = level1._render()
    
    assert rendered == """<script>console.log('Button loaded');</script>
<div id="level1-1" class="test-component">
    <h2>Level 1</h2>
    <div class="nested">
        <p>Nested component ID: level2-1</p>
        <p>Nested component text: None</p>
        <div id="level2-1" class="test-component">
    <h2>Level 2</h2>
    <div class="nested">
        <p>Nested component ID: level3-1</p>
        <p>Nested component text: Level 3 Message</p>
        <div id="level3-1" class="test-component">
    <div class="text">Level 3 Message</div>
</div>

    </div>
</div>

    </div>
</div>
"""

