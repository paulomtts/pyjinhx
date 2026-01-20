import pytest
from markupsafe import Markup

from pyjinhx.base import NestedComponentWrapper
from tests.ui.unified_component import UnifiedComponent


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<span>Test HTML</span>", Markup("<span>Test HTML</span>")),
        ("<div>Content</div>", "<div>Content</div>"),
    ],
)
def test_object_str_method(html: str, expected):
    obj = NestedComponentWrapper(html=html, props=None)

    assert obj.html == html
    assert obj.props is None
    assert str(obj) == expected


def test_object_with_component_props():
    component = UnifiedComponent(id="obj-test-1", text="Object Test")

    obj = NestedComponentWrapper(html="<div>Rendered</div>", props=component)

    assert obj.html == "<div>Rendered</div>"
    assert obj.props == component
    assert obj.props.id == "obj-test-1"
    assert obj.props.text == "Object Test"


