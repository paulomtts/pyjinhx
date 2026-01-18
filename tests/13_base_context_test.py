from tests.ui.unified_component import UnifiedComponent


def test_base_context_parameter():
    base_context = {"global_var": "Global Value", "count": 42}
    
    component = UnifiedComponent(
        id="context-1",
        text="Context Test"
    )
    
    template_source = """
    <div id="{{ id }}">
        <p>{{ text }}</p>
        <p>Global: {{ global_var }}</p>
        <p>Count: {{ count }}</p>
    </div>
    """
    
    rendered = component._render(source=template_source, base_context=base_context)
    
    assert "Context Test" in str(rendered)
    assert "Global Value" in str(rendered)
    assert "42" in str(rendered)


def test_context_merging_with_nested():
    base_context = {"shared": "Shared Value"}
    
    nested = UnifiedComponent(id="nested-context-1", text="Nested")
    
    component = UnifiedComponent(
        id="parent-context-1",
        title="Parent",
        nested=nested
    )
    
    template_source = """
    <div id="{{ id }}">
        <h1>{{ title }}</h1>
        <p>Shared: {{ shared }}</p>
        {{ nested }}
    </div>
    """
    
    rendered = component._render(source=template_source, base_context=base_context)
    
    assert "Parent" in str(rendered)
    assert "Shared Value" in str(rendered)
    assert "nested-context-1" in str(rendered)


def test_context_with_registry_components():
    base_context = {"custom": "Custom Value"}
    
    UnifiedComponent(id="global_context", text="Global")
    
    component = UnifiedComponent(
        id="registry-context-1",
        text="Test"
    )
    
    template_source = """
    <div id="{{ id }}">
        <p>{{ text }}</p>
        <p>Custom: {{ custom }}</p>
        {% if global_context %}
        <div>{{ global_context }}</div>
        {% endif %}
    </div>
    """
    
    rendered = component._render(source=template_source, base_context=base_context)
    
    assert "Test" in str(rendered)
    assert "Custom Value" in str(rendered)
    assert "Global" in str(rendered)

