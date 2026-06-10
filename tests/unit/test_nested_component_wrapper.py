from pyjinhx.base import NestedComponentWrapper
from tests.ui.unified_component import UnifiedComponent


def test_wrapper_str_renders_html_in_template_context():
    """str() on the wrapper emits the html field; inside a Jinja template
    that html appears verbatim (not escaped), and props exposes the original
    component's fields so {{ nested.props.id }} and {{ nested }} both work."""
    child = UnifiedComponent(id="child-str-1", text="hello")
    parent = UnifiedComponent(id="parent-str-1", title="Parent", nested=child)

    rendered = str(parent.render())

    # The child's rendered HTML appears in the parent's output
    assert 'id="child-str-1"' in rendered
    # The wrapper's props expose the original instance fields via template
    assert "Nested component ID: child-str-1" in rendered
    assert "Nested component text: hello" in rendered


def test_object_with_component_props():
    component = UnifiedComponent(id="obj-test-1", text="Object Test")

    obj = NestedComponentWrapper(html="<div>Rendered</div>", props=component)

    assert obj.html == "<div>Rendered</div>"
    assert obj.props == component
    assert obj.props.id == "obj-test-1"
    assert obj.props.text == "Object Test"
