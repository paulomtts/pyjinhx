"""Tests for the render-chain cycle guard (nesting/load chains only, ADR 0004)."""

from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx.component import BaseComponent, _pascal_to_snake
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.render import render
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


class PJXCycleSelf(BaseComponent):
    pass


class PJXCycleA(BaseComponent):
    pass


class PJXCycleB(BaseComponent):
    pass


class PJXCycleLongA(BaseComponent):
    pass


class PJXCycleLongB(BaseComponent):
    pass


class PJXCycleLongC(BaseComponent):
    pass


class PJXAcyclicA(BaseComponent):
    pass


class PJXAcyclicB(BaseComponent):
    pass


class PJXAcyclicC(BaseComponent):
    pass


class PJXDiamond(BaseComponent):
    pass


class PJXPassthroughCycle(BaseComponent):
    pass


class PJXCardL2(BaseComponent):
    depth: str = ""


class PJXRowL2(BaseComponent):
    depth: str = ""


TEMPLATES = {
    PJXCycleSelf: "cycle_self.html",
    PJXCycleA: "cycle_a.html",
    PJXCycleB: "cycle_b.html",
    PJXCycleLongA: "cycle_long_a.html",
    PJXCycleLongB: "cycle_long_b.html",
    PJXCycleLongC: "cycle_long_c.html",
    PJXAcyclicA: "cycle_acyclic_a.html",
    PJXAcyclicB: "cycle_acyclic_b.html",
    PJXAcyclicC: "cycle_acyclic_c.html",
    PJXDiamond: "cycle_diamond.html",
    PJXPassthroughCycle: "cycle_passthrough.html",
    PJXCardL2: "cycle_card_l2.html",
    PJXRowL2: "cycle_row_l2.html",
}

for _cls, _template in TEMPLATES.items():
    _cls.__pjx_descriptor__ = descriptor_for(_cls, _template)


@pytest.fixture(autouse=True)
def registry():
    """Each test sees exactly the fixture components, keyed as discovery keys them."""
    discovery._registry.mapping = {
        _pascal_to_snake(cls.__name__): cls for cls in TEMPLATES
    }
    yield
    discovery._registry.mapping = {}


@pytest.fixture
def session():
    return RenderSession(template_dir="tests/templates")


def test_direct_self_cycle_raises(session):
    with pytest.raises(ValueError) as err:
        render(PJXCycleSelf(), session)
    assert "cycle detected: PJXCycleSelf -> PJXCycleSelf" in str(err.value)


def test_indirect_cycle_names_the_whole_chain(session):
    with pytest.raises(ValueError) as err:
        render(PJXCycleA(), session)
    assert "cycle detected: PJXCycleA -> PJXCycleB -> PJXCycleA" in str(err.value)


def test_longer_cycle_names_the_chain_in_order(session):
    with pytest.raises(ValueError) as err:
        render(PJXCycleLongA(), session)
    assert (
        "cycle detected: PJXCycleLongA -> PJXCycleLongB -> PJXCycleLongC "
        "-> PJXCycleLongA" in str(err.value)
    )


def test_cycle_error_keeps_the_existing_prefix(session):
    with pytest.raises(ValueError) as err:
        render(PJXCycleA(), session)
    assert str(err.value).startswith("PJXCycleA (template: cycle_a.html): ")


def test_acyclic_nesting_still_renders(session):
    assert render(PJXAcyclicA(), session) == (
        '<div class="aa"><div class="ab"><span class="ac">leaf</span></div></div>'
    )


def test_same_component_on_two_sibling_paths_is_not_a_cycle(session):
    branch = '<div class="ab"><span class="ac">leaf</span></div>'
    assert (
        render(PJXDiamond(), session) == f'<div class="diamond">{branch}{branch}</div>'
    )


def test_passthrough_sibling_does_not_mask_the_cycle(session):
    with pytest.raises(ValueError) as err:
        render(PJXPassthroughCycle(), session)
    assert "cycle detected: PJXCycleSelf -> PJXCycleSelf" in str(err.value)


def test_same_class_at_two_depths_on_one_path_is_not_a_cycle(session):
    assert render(PJXCardL2(depth="1"), session) == (
        '<div class="card"><div class="row"><div class="card"></div></div></div>'
    )


def test_unbounded_self_nesting_raises_before_the_recursion_limit(session):
    # RecursionError is not a ValueError, so a stack blowup fails this outright.
    with pytest.raises(ValueError) as err:
        render(PJXCycleSelf(), session)
    assert "cycle detected: PJXCycleSelf -> PJXCycleSelf" in str(err.value)
