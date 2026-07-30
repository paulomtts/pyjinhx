"""Tests for render_context module."""
import pytest
from pathlib import Path
from pydantic import BaseModel

from pyjinhx2.component import BaseComponent, Slot
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.markers import ComponentNode
from pyjinhx2.render_context import build_context


def test_component_node_marker_identity():
    """ComponentNode is not a string so Jinja filters fail fast."""

    class DummyComponent(BaseComponent):
        pass

    comp = DummyComponent()
    node = ComponentNode(comp)

    # Verify it's not a string
    assert not isinstance(node, str)
    # Verify it holds the component reference
    assert node.component is comp
    # Verify len() fails (as Jinja would try)
    with pytest.raises(TypeError):
        len(node)
