"""The tier-2 render cache as render_level() actually uses it: the class-level
off-switch, the resolve/read/write seam, and the slot-disqualification rule.

Full behavioral coverage of the render cache is #821's; what is pinned here is
the wiring — that render_level consults the backend at all, that it stops
consulting it when told to, and that nothing it caches can splice wrong.
"""

from pathlib import Path
from typing import Any

import pytest

from pyjinhx._component import BaseComponent, Children, Slot
from pyjinhx.config import configure_pyjinhx, current_settings
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.reactive.backend import CachePolicy, InMemoryCacheBackend
from pyjinhx.render_cache import (
    copy_level_shell,
    holds_spliced_components,
    resolve_render_tier2,
)
from pyjinhx.segments import ChildRef, RenderedLevel


def test_a_plain_component_records_an_explicit_cache_policy():
    class Widget(BaseComponent, cache=CachePolicy(ttl=45)):
        label: str = ""

    assert Widget._pjx_cache_policy == CachePolicy(ttl=45)


def test_a_plain_component_records_an_explicit_opt_out():
    class Widget(BaseComponent, cache=False):
        label: str = ""

    assert Widget._pjx_cache_policy is False


def test_a_plain_component_that_says_nothing_records_none():
    class Widget(BaseComponent):
        label: str = ""

    assert Widget._pjx_cache_policy is None


def test_a_subclass_does_not_inherit_its_parents_cache_policy():
    class Parent(BaseComponent, cache=False):
        label: str = ""

    class Child(Parent):
        label: str = ""

    assert Child._pjx_cache_policy is None


@pytest.fixture
def backend():
    """Publish a fresh in-memory backend for one test, then restore the settings.

    configure_pyjinhx rather than shutdown_pyjinhx, matching
    test_reactive_cache_tier2_wiring.py: a test that asked for a backend should
    not also blow away whatever else the process was configured with.
    """
    previous = current_settings()
    published = InMemoryCacheBackend()
    configure_pyjinhx(previous.merge(cache_backend=published))
    yield published
    configure_pyjinhx(previous)


@pytest.fixture
def no_backend():
    previous = current_settings()
    configure_pyjinhx(previous.merge(cache_backend=None))
    yield
    configure_pyjinhx(previous)


def test_render_tier2_is_off_when_no_backend_is_configured(no_backend: None):
    class Widget(BaseComponent):
        label: str = ""

    assert resolve_render_tier2(Widget) == (None, None)


def test_render_tier2_is_on_by_default_at_the_process_default_ttl(backend: Any):
    class Widget(BaseComponent):
        label: str = ""

    resolved, ttl = resolve_render_tier2(Widget)

    assert resolved is backend
    assert ttl == CachePolicy().ttl == 300


def test_render_tier2_honors_an_explicit_policy_ttl(backend: Any):
    class Widget(BaseComponent, cache=CachePolicy(ttl=45)):
        label: str = ""

    assert resolve_render_tier2(Widget) == (backend, 45)


def test_render_tier2_is_off_for_a_class_that_opted_out(backend: Any):
    class Widget(BaseComponent, cache=False):
        label: str = ""

    assert resolve_render_tier2(Widget) == (None, None)


class _HoleHolder(BaseComponent):
    label: str = "hi"
    body: Slot = ""
    content: Children = ""


class _Inner(BaseComponent):
    pass


def _attach(
    cls: type[BaseComponent],
    template_path: Path,
    *,
    slot_fields: frozenset[str] = frozenset(),
    children_field: str | None = None,
) -> None:
    """Point a class at a tmp-path template, as test_render_cache_key.py does."""
    cls.__pjx_descriptor__ = ClassDescriptor(
        template_path=template_path,
        slot_fields=slot_fields,
        children_field=children_field,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


def test_a_string_in_a_slot_field_is_not_a_spliced_component(tmp_path: Path):
    template = tmp_path / "holder.html"
    template.write_text("<div>{{ body }}</div>", encoding="utf-8")
    _attach(_HoleHolder, template, slot_fields=frozenset({"body"}), children_field="content")

    assert holds_spliced_components(_HoleHolder(body="plain", content="text")) is False


def test_a_component_in_a_slot_field_is_a_spliced_component(tmp_path: Path):
    template = tmp_path / "holder.html"
    template.write_text("<div>{{ body }}</div>", encoding="utf-8")
    _attach(_HoleHolder, template, slot_fields=frozenset({"body"}), children_field="content")

    assert holds_spliced_components(_HoleHolder(body=_Inner(), content="text")) is True


def test_a_component_in_the_children_field_is_a_spliced_component(tmp_path: Path):
    template = tmp_path / "holder.html"
    template.write_text("<div>{{ content }}</div>", encoding="utf-8")
    _attach(_HoleHolder, template, slot_fields=frozenset({"body"}), children_field="content")

    assert holds_spliced_components(_HoleHolder(body="x", content=[_Inner()])) is True


def test_copying_a_level_shell_gives_an_independently_mutable_segment_list():
    ref = ChildRef(tag="PJXIcon", attrs={}, inner=None)
    original = RenderedLevel(segments=["<div>", ref, "</div>"], root_span=(0, 5), descriptor=None)

    copy = copy_level_shell(original)
    copy.segments[1] = "filled"

    assert original.segments[1] is ref
    assert copy.root_span == original.root_span
    assert copy.descriptor is original.descriptor
