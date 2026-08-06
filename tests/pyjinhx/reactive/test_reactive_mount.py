"""Automatic load() on ChildRef-mounted ReactiveComponent instances.

_fill_children resolves each ChildRef against the registry; a reactive class is
recognised by its ``_pjx_key_field`` marker and built by calling
``cls.load(**key_args)`` there and then, so the instance that reaches
render_level's recursion is already the memoized, fully populated one. A plain
BaseComponent child must be unaffected — it carries no marker at all.
"""

from pathlib import Path
from typing import Annotated

import pytest
from pydantic import Field

from pyjinhx import discovery
from pyjinhx._component import (
    BaseComponent,
    _pascal_to_snake,
    _resolve_json_coercible_fields,
)
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.rendering import render, render_level
from pyjinhx.segments import serialize
from pyjinhx.session import RenderSession, request_scope

_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"

_load_calls: list[int] = []


class PJXReactiveWidget(ReactiveComponent):
    @classmethod
    def load(cls) -> "PJXReactiveWidget":
        _load_calls.append(1)
        return cls()


class PJXPlainWidget(BaseComponent):
    pass


def _descriptor_for(cls: type[BaseComponent], template: str) -> ClassDescriptor:
    return ClassDescriptor(
        template_path=_TEMPLATE_DIR / template,
        slot_fields=frozenset(),
        json_coercible_fields=_resolve_json_coercible_fields(cls),
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


class PJXKeyedWidget(ReactiveComponent):
    row_id: Annotated[int, PjxKey()] = 0
    label: str = "from-load"

    @classmethod
    def load(cls, row_id: int = 0) -> "PJXKeyedWidget":
        _load_calls.append(row_id)
        return cls(row_id=row_id, label=f"loaded-{row_id}")


PJXKeyedWidget.__pjx_descriptor__ = _descriptor_for(
    PJXKeyedWidget, "reactive_keyed_widget.html"
)


class KeyedTwiceContainer(BaseComponent):
    pass


KeyedTwiceContainer.__pjx_descriptor__ = _descriptor_for(
    KeyedTwiceContainer, "reactive_keyed_twice.html"
)


class KeyedOverrideContainer(BaseComponent):
    pass


KeyedOverrideContainer.__pjx_descriptor__ = _descriptor_for(
    KeyedOverrideContainer, "reactive_keyed_override.html"
)


class PJXKeyedListWidget(ReactiveComponent):
    row_id: Annotated[int, PjxKey()] = 0
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def load(cls, row_id: int = 0) -> "PJXKeyedListWidget":
        _load_calls.append(row_id)
        return cls(row_id=row_id, tags=["loaded"])


PJXKeyedListWidget.__pjx_descriptor__ = _descriptor_for(
    PJXKeyedListWidget, "reactive_keyed_list_widget.html"
)


class KeyedJsonAttrContainer(BaseComponent):
    pass


KeyedJsonAttrContainer.__pjx_descriptor__ = _descriptor_for(
    KeyedJsonAttrContainer, "reactive_keyed_json_attr.html"
)


@pytest.fixture(autouse=True)
def _registered_tags():
    """Register the container/widget tags this module's templates reference."""
    discovery._registry.mapping = {
        _pascal_to_snake(cls.__name__): cls
        for cls in (
            ContainerComp,
            PJXReactiveWidget,
            PJXPlainWidget,
            PJXKeyedWidget,
            KeyedTwiceContainer,
            KeyedOverrideContainer,
            PJXKeyedListWidget,
            KeyedJsonAttrContainer,
        )
    }
    _load_calls.clear()
    yield
    discovery._registry.mapping = {}
    _load_calls.clear()


def test_reactive_child_mounted_via_childref_has_load_run_automatically():
    """No manual load() call anywhere in this test — mounting alone must trigger it."""
    session = RenderSession()
    component = ContainerComp()

    with request_scope():
        render_level(component, session)

    assert len(_load_calls) == 1


def test_plain_child_mounted_via_childref_is_unaffected():
    """A plain BaseComponent has no load() and no reactive marker; mounting it
    must not raise and must not add anything to the reactive load-call log."""
    session = RenderSession()

    class OnlyPlainContainer(BaseComponent):
        pass

    OnlyPlainContainer.__pjx_descriptor__ = _descriptor_for(
        OnlyPlainContainer, "container_only_plain.html"
    )
    discovery._registry.mapping["only_plain_container"] = OnlyPlainContainer

    result = render_level(OnlyPlainContainer(), session)

    assert "plain" in "".join(str(s) for s in result.segments)
    assert _load_calls == []


def test_same_key_twice_in_one_render_runs_load_once():
    """Both tags name row_id=7, so the second _fill_children call must hit the
    request cache #726 installed and reuse the first instance's state."""
    session = RenderSession()

    with request_scope():
        result = render_level(KeyedTwiceContainer(), session)

    assert _load_calls == [7]
    assert serialize(result).count("loaded-7") == 2


def test_non_key_attrs_are_applied_onto_the_loaded_instance():
    """label is not the key field, so load() never sees it; _fill_children must
    set it on the returned instance, overriding what load() itself produced."""
    session = RenderSession()

    with request_scope():
        result = render_level(KeyedOverrideContainer(), session)

    assert _load_calls == [3]
    assert "overridden" in serialize(result)
    assert "loaded-3" not in serialize(result)


def test_zero_key_reactive_child_is_loaded_with_no_args():
    """PJXReactiveWidget declares no PjxKey field, so the key-arg split must
    produce an empty kwargs dict rather than a KeyError or a stray positional."""
    session = RenderSession()

    with request_scope():
        render_level(ContainerComp(), session)

    assert len(_load_calls) == 1


def test_reactive_root_passed_straight_to_render_is_loaded_automatically():
    """A component passed as the request's own root never goes through
    _fill_children (only a ChildRef-discovered child does), so render() itself
    must route it through load() before rendering — no manual pjx_mount()
    call needed anywhere in this test."""
    session = RenderSession()

    with request_scope():
        html = render(PJXKeyedWidget(row_id=9), session=session)

    assert _load_calls == [9]
    assert "loaded-9" in html


def test_json_string_non_key_attr_is_coerced_before_assignment():
    """tags is typed list[str]; the tag passes it as a JSON-looking string, so
    _load_reactive_child must run the same JSON coercion _instantiate_child gets
    for free from construction, or validate_assignment rejects the raw string."""
    session = RenderSession()

    with request_scope():
        result = render_level(KeyedJsonAttrContainer(), session)

    assert serialize(result).count("override-tag") == 1
