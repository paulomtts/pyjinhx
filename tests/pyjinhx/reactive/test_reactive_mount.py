"""Automatic load() on ChildRef-mounted ReactiveComponent instances.

render_level() instantiates each resolved ChildRef and recurses into it; a
ReactiveComponent child must have its cache-routed load() run before that
recursive render, with no manual call from the template author. A plain
BaseComponent child must be unaffected — it declares no load() at all.
"""

from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx.component import BaseComponent, _pascal_to_snake
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.reactive.component import ReactiveComponent
from pyjinhx.render import render_level
from pyjinhx.session import RenderSession

_load_calls: list[str] = []


class PJXReactiveWidget(ReactiveComponent):
    def load(self) -> None:
        _load_calls.append(self.id)


class PJXPlainWidget(BaseComponent):
    pass


def _descriptor_for(cls: type[BaseComponent], template: str) -> ClassDescriptor:
    return ClassDescriptor(
        template_path=Path(template),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


PJXReactiveWidget.__pjx_descriptor__ = _descriptor_for(
    PJXReactiveWidget, "reactive_widget.html"
)
PJXPlainWidget.__pjx_descriptor__ = _descriptor_for(PJXPlainWidget, "plain_widget.html")


class ContainerComp(BaseComponent):
    pass


ContainerComp.__pjx_descriptor__ = _descriptor_for(
    ContainerComp, "reactive_mount_container.html"
)


@pytest.fixture(autouse=True)
def _registered_tags():
    """Register the container/widget tags this module's templates reference."""
    discovery._registry.mapping = {
        _pascal_to_snake(cls.__name__): cls
        for cls in (ContainerComp, PJXReactiveWidget, PJXPlainWidget)
    }
    _load_calls.clear()
    yield
    discovery._registry.mapping = {}
    _load_calls.clear()


def test_reactive_child_mounted_via_childref_has_load_run_automatically():
    """No manual load() call anywhere in this test — mounting alone must trigger it."""
    session = RenderSession(template_dir="tests/templates")
    component = ContainerComp()

    render_level(component, session)

    assert len(_load_calls) == 1


def test_plain_child_mounted_via_childref_is_unaffected():
    """A plain BaseComponent has no load() and no pjx_mount() override; mounting
    it must not raise and must not add anything to the reactive load-call log."""
    session = RenderSession(template_dir="tests/templates")

    class OnlyPlainContainer(BaseComponent):
        pass

    OnlyPlainContainer.__pjx_descriptor__ = _descriptor_for(
        OnlyPlainContainer, "container_only_plain.html"
    )
    discovery._registry.mapping["only_plain_container"] = OnlyPlainContainer

    result = render_level(OnlyPlainContainer(), session)

    assert "plain" in "".join(str(s) for s in result.segments)
    assert _load_calls == []


def test_base_component_pjx_mount_is_noop():
    """The base hook must do nothing at all: render.py calls it on every child,
    so any side effect here would leak into every plain component's render."""

    class Plain(BaseComponent):
        pass

    component = Plain()
    before = component.model_dump()

    assert component.pjx_mount() is None
    assert component.model_dump() == before
    assert _load_calls == []
