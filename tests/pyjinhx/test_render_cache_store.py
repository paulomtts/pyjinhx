"""Unit tests for tier-2 render-cache store/restore and asset replay.

Component classes and descriptor builders are module-level on purpose: the
DiskCacheBackend path pickles whatever it is handed, and a class defined
inside a test function cannot be pickled by reference.
"""

import pickle
from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx._component import BaseComponent
from pyjinhx.classless import component
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.integrations.diskcache import DiskCacheBackend
from pyjinhx.reactive.backend import MISS, InMemoryCacheBackend
from pyjinhx.render_cache import (
    replay_asset_accumulation,
    restore_rendered_level,
    store_rendered_level,
)
from pyjinhx.rendering import render_level
from pyjinhx.segments import ChildRef, RenderedLevel, serialize
from pyjinhx.session import RenderSession


class _StorePlain(BaseComponent):
    label: str = "hi"


def _descriptor(
    cls: type[BaseComponent],
    template_path: Path,
    *,
    css_paths: tuple[Path, ...] = (),
    js_paths: tuple[Path, ...] = (),
) -> ClassDescriptor:
    return ClassDescriptor(
        template_path=template_path,
        slot_fields=frozenset(),
        children_field=None,
        css_paths=css_paths,
        js_paths=js_paths,
        strict=True,
        provenance={"template": cls},
    )


def _level(descriptor: ClassDescriptor) -> RenderedLevel:
    return RenderedLevel(
        segments=[
            '<div class="root">',
            ChildRef(tag="PJXButton", attrs={"label": "go"}, inner=None),
            "</div>",
        ],
        root_span=(0, 19),
        descriptor=descriptor,
    )


@pytest.fixture
def template(tmp_path: Path) -> Path:
    path = tmp_path / "store_template.html"
    path.write_text("<div>{{ label }}</div>", encoding="utf-8")
    return path


def test_in_memory_round_trip(template: Path):
    """Store then restore through InMemoryCacheBackend hands the level back."""
    backend = InMemoryCacheBackend()
    level = _level(_descriptor(_StorePlain, template))

    store_rendered_level(backend, "k", level, ttl=300)
    restored = restore_rendered_level(backend, "k")

    assert isinstance(restored, RenderedLevel)
    assert restored.root_span == (0, 19)
    assert restored.segments[0] == '<div class="root">'
    assert restored.segments[2] == "</div>"


def test_disk_round_trip_survives_pickling(tmp_path: Path, template: Path):
    """The pickling backend returns a copy whose fields all survive."""
    backend = DiskCacheBackend(tmp_path / "cache")
    css = (template.parent / "a.css",)
    js = (template.parent / "a.js",)
    level = _level(_descriptor(_StorePlain, template, css_paths=css, js_paths=js))

    store_rendered_level(backend, "k", level, ttl=300)
    restored = restore_rendered_level(backend, "k")
    backend.close()

    assert isinstance(restored, RenderedLevel)
    assert restored is not level
    assert restored.root_span == level.root_span
    assert restored.segments[0] == level.segments[0]
    assert restored.segments[2] == level.segments[2]
    assert restored.descriptor.template_path == template
    assert restored.descriptor.css_paths == css
    assert restored.descriptor.js_paths == js
    assert restored.descriptor.provenance["template"] is _StorePlain


def test_restored_level_keeps_childref_unresolved(tmp_path: Path, template: Path):
    """A ChildRef hole comes back a ChildRef, not text and not a component."""
    backend = DiskCacheBackend(tmp_path / "cache")
    level = _level(_descriptor(_StorePlain, template))

    store_rendered_level(backend, "k", level, ttl=300)
    restored = restore_rendered_level(backend, "k")
    backend.close()

    assert isinstance(restored, RenderedLevel)
    hole = restored.segments[1]
    assert isinstance(hole, ChildRef)
    assert hole.tag == "PJXButton"
    assert hole.attrs == {"label": "go"}
    assert hole.inner is None


def test_miss_returns_sentinel():
    """A key nothing was stored under answers MISS, not an exception."""
    backend = InMemoryCacheBackend()

    assert restore_rendered_level(backend, "nothing-here") is MISS


def test_store_is_untagged(template: Path):
    """Nothing tags a non-reactive entry, so evict() by any tag misses it."""
    backend = InMemoryCacheBackend()
    level = _level(_descriptor(_StorePlain, template))

    store_rendered_level(backend, "k", level, ttl=300)
    backend.evict(["anything"])

    assert restore_rendered_level(backend, "k") is not MISS


def test_ttl_expiry_is_a_miss(template: Path):
    """A stored level past its ttl reads back as MISS."""
    now = [1000.0]
    backend = InMemoryCacheBackend(clock=lambda: now[0])
    store_rendered_level(backend, "k", _level(_descriptor(_StorePlain, template)), ttl=5)

    now[0] = 1006.0

    assert restore_rendered_level(backend, "k") is MISS


def test_backend_put_failure_propagates(template: Path):
    """A backend that raises on put is not swallowed here."""

    class _Exploding(InMemoryCacheBackend):
        def put(self, key, value, *, tags, ttl):
            raise OSError("disk on fire")

    with pytest.raises(OSError, match="disk on fire"):
        store_rendered_level(
            _Exploding(), "k", _level(_descriptor(_StorePlain, template)), ttl=300
        )


def test_foreign_entry_raises():
    """A non-level under the key raises rather than being served or downgraded."""
    backend = InMemoryCacheBackend()
    backend.put("k", {"not": "a level"}, tags=(), ttl=None)

    with pytest.raises(ValueError, match="not a RenderedLevel but a dict"):
        restore_rendered_level(backend, "k")


def test_broken_segment_raises(template: Path):
    """A segment that did not survive storage raises, naming its position."""
    backend = InMemoryCacheBackend()
    level = _level(_descriptor(_StorePlain, template))
    level.segments[1] = object()  # pyright: ignore[reportArgumentType]
    backend.put("k", level, tags=(), ttl=None)

    with pytest.raises(ValueError, match="segment 1"):
        restore_rendered_level(backend, "k")


def test_backend_get_failure_propagates():
    """A backend that raises on get is not turned into a miss here."""

    class _Exploding(InMemoryCacheBackend):
        def get(self, key):
            raise OSError("disk on fire")

    with pytest.raises(OSError, match="disk on fire"):
        restore_rendered_level(_Exploding(), "k")


def test_replay_adds_descriptor_assets(template: Path):
    """The level's descriptor paths land in the session's asset sets."""
    css = (template.parent / "a.css",)
    js = (template.parent / "a.js",)
    level = _level(_descriptor(_StorePlain, template, css_paths=css, js_paths=js))
    session = RenderSession()

    replay_asset_accumulation(level, session)

    assert session.css_assets == set(css)
    assert session.js_assets == set(js)


def test_replay_is_idempotent(template: Path):
    """A second replay of the same level changes nothing."""
    css = (template.parent / "a.css",)
    js = (template.parent / "a.js",)
    level = _level(_descriptor(_StorePlain, template, css_paths=css, js_paths=js))
    session = RenderSession()

    replay_asset_accumulation(level, session)
    replay_asset_accumulation(level, session)

    assert session.css_assets == set(css)
    assert session.js_assets == set(js)


def test_replay_never_fires_rendered_subscribers(template: Path):
    """The reactive-shaped on_rendered hooks stay untouched on a cache hit."""
    calls: list[object] = []
    session = RenderSession()
    session.on_rendered.append(lambda component, level, sess: calls.append(component))
    level = _level(
        _descriptor(
            _StorePlain,
            template,
            css_paths=(template.parent / "a.css",),
            js_paths=(),
        )
    )

    replay_asset_accumulation(level, session)

    assert calls == []
    assert session.css_assets == {template.parent / "a.css"}


class _StoreLeaf(BaseComponent):
    label: str = "click me"


def test_real_pipeline_level_round_trips(tmp_path: Path):
    """A level render_level actually produced survives the pickling backend.

    A leaf component has no child tags, so the level render_level returns is
    byte-for-byte the level its parse phase built - the shape tier 2 caches -
    without reaching into _fill_children to capture it mid-flight.
    """
    template = tmp_path / "leaf.html"
    template.write_text("<button>{{ label }}</button>", encoding="utf-8")
    _StoreLeaf.__pjx_descriptor__ = _descriptor(
        _StoreLeaf,
        template,
        css_paths=(tmp_path / "leaf.css",),
        js_paths=(tmp_path / "leaf.js",),
    )
    session = RenderSession()
    level = render_level(_StoreLeaf(), session)

    backend = DiskCacheBackend(tmp_path / "cache")
    store_rendered_level(backend, "k", level, ttl=300)
    restored = restore_rendered_level(backend, "k")
    backend.close()

    assert isinstance(restored, RenderedLevel)
    assert serialize(restored) == serialize(level)
    assert restored.root_span == level.root_span

    replay_session = RenderSession()
    replay_asset_accumulation(restored, replay_session)
    assert replay_session.css_assets == {tmp_path / "leaf.css"}
    assert replay_session.js_assets == {tmp_path / "leaf.js"}


def test_classless_component_level_fails_loudly_on_the_disk_backend(tmp_path: Path):
    """A generated class's descriptor cannot be pickled, and says so.

    component() builds a class in a synthetic module that is registered in
    sys.modules but never given the class as an attribute, so pickle's
    by-reference lookup for descriptor.provenance finds nothing. The disk
    backend surfaces that as its own error rather than storing a half-level;
    that is the behavior tier 2 gets, and #820's wiring has to live with a
    generated component simply not caching rather than caching wrongly.
    """
    saved_mapping = discovery._registry.mapping
    saved_template_dir = discovery._registry.template_dir
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    try:
        (tmp_path / "widget.pjx").write_text("<div>hello</div>", encoding="utf-8")
        cls = component("Widget", template_dir=tmp_path)
        level = RenderedLevel(
            segments=["<div>hello</div>"],
            root_span=(0, 5),
            descriptor=cls.__pjx_descriptor__,
        )
        backend = DiskCacheBackend(tmp_path / "cache")

        with pytest.raises((pickle.PicklingError, AttributeError)):
            store_rendered_level(backend, "k", level, ttl=300)

        backend.close()
    finally:
        discovery._registry.mapping = saved_mapping
        discovery._registry.template_dir = saved_template_dir
