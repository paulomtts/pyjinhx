"""render_level fires session.on_rendered once per component, bottom-up.

The ordering is load-bearing: subscribers accumulate session state (assets, the
reactive instance registry) and each one runs knowing its children already ran.
"""

from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx.component import BaseComponent
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.render import render, render_level
from pyjinhx.segments import RenderedLevel
from pyjinhx.session import RenderSession


def descriptor_for(cls: type[BaseComponent], template: str) -> ClassDescriptor:
    """Attach a minimal descriptor pointing at a fixture template."""
    return ClassDescriptor(
        template_path=Path(template),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


class PJXNestedLeaf(BaseComponent):
    label: str = ""


PJXNestedLeaf.__pjx_descriptor__ = descriptor_for(PJXNestedLeaf, "nested_leaf.html")


class PJXNestedMid(BaseComponent):
    label: str = ""


PJXNestedMid.__pjx_descriptor__ = descriptor_for(PJXNestedMid, "nested_mid.html")


class PJXNestedRoot(BaseComponent):
    pass


PJXNestedRoot.__pjx_descriptor__ = descriptor_for(PJXNestedRoot, "nested_root.html")


@pytest.fixture(autouse=True)
def registry():
    discovery._registry.mapping = {
        "pjx_nested_leaf": PJXNestedLeaf,
        "pjx_nested_mid": PJXNestedMid,
    }
    yield
    discovery._registry.mapping = {}


@pytest.fixture
def session():
    return RenderSession(template_dir="tests/templates")


def test_hook_fires_children_before_parents(session):
    """nested_root -> nested_mid -> nested_leaf, so the leaf must be first."""
    order: list[str] = []
    session.on_rendered.append(
        lambda component, level, session: order.append(type(component).__name__)
    )

    render_level(PJXNestedRoot(), session)

    assert order == ["PJXNestedLeaf", "PJXNestedMid", "PJXNestedRoot"]


def test_hook_fires_exactly_once_per_component(session):
    seen: list[BaseComponent] = []
    session.on_rendered.append(lambda component, level, session: seen.append(component))

    render_level(PJXNestedRoot(), session)

    assert len(seen) == 3
    assert len({id(component) for component in seen}) == 3


def test_hook_receives_the_components_own_completed_level(session):
    """Each callback must get the level whose subtree just finished, not the root's."""
    pairs: list[tuple[str, RenderedLevel]] = []
    session.on_rendered.append(
        lambda component, level, session: pairs.append(
            (type(component).__name__, level)
        )
    )

    root_level = render_level(PJXNestedRoot(), session)

    by_name = {name: level for name, level in pairs}
    assert by_name["PJXNestedRoot"] is root_level
    assert by_name["PJXNestedMid"].descriptor is PJXNestedMid.__pjx_descriptor__
    assert by_name["PJXNestedLeaf"].descriptor is PJXNestedLeaf.__pjx_descriptor__
    # The mid level's child slot already holds the finished leaf when mid fires.
    assert isinstance(by_name["PJXNestedMid"].segments[2], RenderedLevel)


def test_leaf_level_is_complete_when_its_own_hook_fires(session):
    """Post-order means no ChildRef holes are left in the level handed over."""
    from pyjinhx.segments import ChildRef

    holes: list[str] = []

    def check(
        component: BaseComponent, level: RenderedLevel, session: RenderSession
    ) -> None:
        if any(isinstance(segment, ChildRef) for segment in level.segments):
            holes.append(type(component).__name__)

    session.on_rendered.append(check)
    render_level(PJXNestedRoot(), session)

    assert holes == []


def test_render_public_api_fires_the_hook_too(session):
    order: list[str] = []
    session.on_rendered.append(
        lambda component, level, session: order.append(type(component).__name__)
    )

    render(PJXNestedRoot(), session)

    assert order == ["PJXNestedLeaf", "PJXNestedMid", "PJXNestedRoot"]


def test_rendering_with_no_subscribers_still_works(session):
    """The unconditional fire must cost nothing observable when nobody listens."""
    assert session.on_rendered == []

    html = render(PJXNestedRoot(), session)

    assert "leaf" in html
    assert session.on_rendered == []
