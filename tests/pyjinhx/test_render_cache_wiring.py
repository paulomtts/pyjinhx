"""The tier-2 render cache as render_level() actually uses it: the class-level
off-switch, the resolve/read/write seam, and the slot-disqualification rule.

Full behavioral coverage of the render cache is #821's; what is pinned here is
the wiring — that render_level consults the backend at all, that it stops
consulting it when told to, and that nothing it caches can splice wrong.
"""

import os
from pathlib import Path
from typing import Any

import pytest

from pyjinhx import discovery, rendering
from pyjinhx._component import BaseComponent, Children, Slot, _pascal_to_snake
from pyjinhx.config import configure_pyjinhx, current_settings
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.reactive.backend import CachePolicy, InMemoryCacheBackend
from pyjinhx.reactive.backend_health import (
    is_degraded,
    note_failure,
    reset_backend_health,
)
from pyjinhx.render_cache import (
    copy_level_shell,
    holds_spliced_components,
    load_rendered_level,
    render_cache_key,
    resolve_render_tier2,
    save_rendered_level,
)
from pyjinhx.rendering import render_level
from pyjinhx.segments import ChildRef, RenderedLevel, serialize
from pyjinhx.session import RenderSession, accumulate_assets


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
    _attach(
        _HoleHolder, template, slot_fields=frozenset({"body"}), children_field="content"
    )

    assert holds_spliced_components(_HoleHolder(body="plain", content="text")) is False


def test_a_component_in_a_slot_field_is_a_spliced_component(tmp_path: Path):
    template = tmp_path / "holder.html"
    template.write_text("<div>{{ body }}</div>", encoding="utf-8")
    _attach(
        _HoleHolder, template, slot_fields=frozenset({"body"}), children_field="content"
    )

    assert holds_spliced_components(_HoleHolder(body=_Inner(), content="text")) is True


def test_a_component_in_the_children_field_is_a_spliced_component(tmp_path: Path):
    template = tmp_path / "holder.html"
    template.write_text("<div>{{ content }}</div>", encoding="utf-8")
    _attach(
        _HoleHolder, template, slot_fields=frozenset({"body"}), children_field="content"
    )

    assert holds_spliced_components(_HoleHolder(body="x", content=[_Inner()])) is True


def test_copying_a_level_shell_gives_an_independently_mutable_segment_list():
    ref = ChildRef(tag="PJXIcon", attrs={}, inner=None)
    original = RenderedLevel(
        segments=["<div>", ref, "</div>"], root_span=(0, 5), descriptor=None
    )

    copy = copy_level_shell(original)
    copy.segments[1] = "filled"

    assert original.segments[1] is ref
    assert copy.root_span == original.root_span
    assert copy.descriptor is original.descriptor


class SpyBackend(InMemoryCacheBackend):
    """An in-memory backend that records its calls and can be told to fail.

    Mirrors reactive/test_reactive_cache_failure_policy.py's BrokenBackend; kept
    local rather than imported across the reactive/render test split so neither
    file owns the other's fixture.
    """

    def __init__(self, *, fail_get: bool = False, fail_put: bool = False) -> None:
        super().__init__()
        self.fail_get = fail_get
        self.fail_put = fail_put
        self.gets: list[str] = []
        self.puts: list[str] = []

    def get(self, key: str) -> object:
        self.gets.append(key)
        if self.fail_get:
            raise RuntimeError("get is down")
        return super().get(key)

    def put(self, key: str, value: object, *, tags, ttl) -> None:
        self.puts.append(key)
        if self.fail_put:
            raise RuntimeError("put is down")
        super().put(key, value, tags=tags, ttl=ttl)


@pytest.fixture(autouse=True)
def clean_health():
    """Backend health is process-wide: no test may inherit another's flags."""
    reset_backend_health()
    yield
    reset_backend_health()


def _level() -> RenderedLevel:
    return RenderedLevel(segments=["<div></div>"], root_span=(0, 5), descriptor=None)


def test_loading_a_missing_entry_answers_none():
    assert load_rendered_level(SpyBackend(), "k") is None


def test_a_failing_get_answers_none_without_raising():
    spy = SpyBackend(fail_get=True)

    assert load_rendered_level(spy, "k") is None


def test_a_corrupt_entry_still_raises_through_the_facade():
    spy = SpyBackend()
    spy.put("k", "not a level", tags=(), ttl=None)

    with pytest.raises(ValueError, match="not a RenderedLevel"):
        load_rendered_level(spy, "k")


def test_a_degraded_backend_is_not_read_from_until_a_write_lands():
    spy = SpyBackend()
    # Degrade it the way backend_health's contract does, via a failed evict.
    note_failure(spy, "evict", RuntimeError("evict is down"), degrade=True)
    assert load_rendered_level(spy, "k") is None
    assert spy.gets == []

    save_rendered_level(spy, "k", _level(), ttl=None)

    assert is_degraded(spy) is False
    load_rendered_level(spy, "k")
    assert spy.gets == ["k"]


def test_a_failing_put_does_not_raise_and_does_not_clear_degradation():
    spy = SpyBackend(fail_put=True)

    save_rendered_level(spy, "k", _level(), ttl=None)

    assert spy.puts == ["k"]


class _CachedBox(BaseComponent):
    label: str = "hi"


@pytest.fixture(autouse=True)
def reset_registry():
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    yield
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


@pytest.fixture
def box_template(tmp_path: Path) -> Path:
    path = tmp_path / "cached_box.html"
    path.write_text("<div>{{ label }}</div>", encoding="utf-8")
    _attach(_CachedBox, path)
    return path


def test_a_first_render_writes_the_shell_through_to_the_backend(
    backend: InMemoryCacheBackend, box_template: Path
):
    spy = SpyBackend()
    configure_pyjinhx(current_settings().merge(cache_backend=spy))

    rendered = serialize(render_level(_CachedBox(id="a", label="hi"), RenderSession()))

    assert rendered == "<div>hi</div>"
    assert len(spy.puts) == 1
    assert len(spy.gets) == 1


def test_a_second_render_answers_from_the_cache_without_rendering_the_template(
    backend: InMemoryCacheBackend, box_template: Path
):
    session = RenderSession()
    first = serialize(render_level(_CachedBox(id="a", label="hi"), session))
    mtime = box_template.stat().st_mtime
    box_template.write_text("<div>REBUILT</div>", encoding="utf-8")
    os.utime(box_template, (mtime, mtime))

    second = serialize(render_level(_CachedBox(id="a", label="hi"), RenderSession()))

    assert first == "<div>hi</div>"
    assert second == first


def _accumulating_session() -> RenderSession:
    """A fresh RenderSession with the asset accumulator wired to on_rendered.

    accumulate_assets is opt-in per session (see tests/pyjinhx/test_assets.py's
    fixture of the same shape) — a bare RenderSession() never accumulates on a
    live render either, so a test proving a hit "replays what a live render
    would have done" has to compare against a session that actually would.
    """
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    return session


def test_a_hit_replays_the_assets_a_live_render_would_have_emitted(
    backend: InMemoryCacheBackend, tmp_path: Path
):
    css = tmp_path / "box.css"
    js = tmp_path / "box.js"
    template = tmp_path / "asset_box.html"
    template.write_text("<div>{{ label }}</div>", encoding="utf-8")
    _CachedBox.__pjx_descriptor__ = ClassDescriptor(
        template_path=template,
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(css,),
        js_paths=(js,),
        strict=True,
        provenance={"template": _CachedBox},
    )
    render_level(_CachedBox(id="a", label="hi"), _accumulating_session())

    warm = _accumulating_session()
    render_level(_CachedBox(id="a", label="hi"), warm)

    assert warm.css_assets == {css}
    assert warm.js_assets == {js}


def test_a_hit_accumulates_nothing_when_the_session_never_asked_for_it(
    backend: InMemoryCacheBackend, tmp_path: Path
):
    """D6: a hit must not do more than the live path would for this session.

    accumulate_assets is opt-in (see _accumulating_session above); a session
    that never subscribed it gets nothing on a live render, so a cache hit on
    an equivalent, un-wired session must also get nothing — not a forced
    accumulation the caller never asked for.
    """
    css = tmp_path / "unwired_box.css"
    template = tmp_path / "unwired_box.html"
    template.write_text("<div>{{ label }}</div>", encoding="utf-8")
    _CachedBox.__pjx_descriptor__ = ClassDescriptor(
        template_path=template,
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(css,),
        js_paths=(),
        strict=True,
        provenance={"template": _CachedBox},
    )
    # Primes the cache (a miss, on an un-wired session — nothing accumulates,
    # which is the baseline this test is protecting).
    priming = RenderSession()
    render_level(_CachedBox(id="a", label="hi"), priming)
    assert priming.css_assets == set()

    # A hit, on a second un-wired session — must match the miss above, not
    # force accumulation this session never subscribed to.
    warm = RenderSession()
    render_level(_CachedBox(id="a", label="hi"), warm)

    assert warm.css_assets == set()


def test_a_hit_does_not_fill_the_children_of_the_cached_entry(
    backend: InMemoryCacheBackend, tmp_path: Path
):
    """The entry keeps its holes: filling the restored copy must not edit it."""
    icon = tmp_path / "icon.html"
    icon.write_text("<span>i</span>", encoding="utf-8")
    _attach(_Inner, icon)
    holder = tmp_path / "holder_tag.html"
    holder.write_text("<div>{{ label }}<Inner/></div>", encoding="utf-8")
    _attach(_CachedBox, holder)
    discovery._registry.mapping = {_pascal_to_snake("Inner"): _Inner}

    first = serialize(render_level(_CachedBox(id="a", label="hi"), RenderSession()))
    second = serialize(render_level(_CachedBox(id="a", label="hi"), RenderSession()))
    third = serialize(render_level(_CachedBox(id="a", label="hi"), RenderSession()))

    assert first == second == third == "<div>hi<span>i</span></div>"


def test_cache_false_never_touches_the_backend(box_template: Path):
    class OptedOut(BaseComponent, cache=False):
        label: str = "hi"

    _attach(OptedOut, box_template)
    spy = SpyBackend()
    previous = current_settings()
    configure_pyjinhx(previous.merge(cache_backend=spy))
    try:
        render_level(OptedOut(id="a", label="hi"), RenderSession())
        render_level(OptedOut(id="a", label="hi"), RenderSession())
    finally:
        configure_pyjinhx(previous)

    assert spy.gets == []
    assert spy.puts == []


def test_no_backend_configured_never_computes_a_key(
    no_backend: None, box_template: Path, monkeypatch: pytest.MonkeyPatch
):
    def boom(component: object) -> str:
        raise AssertionError("render_cache_key was computed with tier 2 off")

    monkeypatch.setattr(rendering, "render_cache_key", boom)

    assert serialize(render_level(_CachedBox(id="a", label="hi"), RenderSession())) == (
        "<div>hi</div>"
    )


def test_a_component_valued_slot_is_never_cached_and_splices_every_time(
    backend: InMemoryCacheBackend, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The (b) disqualification: no key, no entry, and correct markup twice."""
    inner = tmp_path / "inner.html"
    inner.write_text("<span>i</span>", encoding="utf-8")
    _attach(_Inner, inner)
    holder = tmp_path / "slot_holder.html"
    holder.write_text("<div>{{ body }}</div>", encoding="utf-8")
    _attach(
        _HoleHolder, holder, slot_fields=frozenset({"body"}), children_field="content"
    )

    real_render_cache_key = rendering.render_cache_key

    def guarded(component: object) -> str:
        # Scoped to _HoleHolder itself, not the whole tree: its spliced _Inner
        # child is an ordinary cacheable component and legitimately gets its
        # own key computed on its own render_level call — what D1 disqualifies
        # is only the parent instance holding the component-valued slot.
        if isinstance(component, _HoleHolder):
            raise AssertionError(  # noqa: TRY004
                "a component-valued slot must never be keyed"
            )
        return real_render_cache_key(component)

    monkeypatch.setattr(rendering, "render_cache_key", guarded)

    first = serialize(render_level(_HoleHolder(id="a", body=_Inner()), RenderSession()))
    second = serialize(
        render_level(_HoleHolder(id="a", body=_Inner()), RenderSession())
    )

    assert first == second == "<div><span>i</span></div>"
    assert "pjx-slot-" not in first


def test_a_failing_get_degrades_the_backend_without_failing_the_render(
    box_template: Path, caplog: pytest.LogCaptureFixture
):
    spy = SpyBackend(fail_get=True)
    previous = current_settings()
    configure_pyjinhx(previous.merge(cache_backend=spy))
    try:
        with caplog.at_level("WARNING", logger="pyjinhx"):
            rendered = serialize(
                render_level(_CachedBox(id="a", label="hi"), RenderSession())
            )
    finally:
        configure_pyjinhx(previous)

    assert rendered == "<div>hi</div>"
    assert len(caplog.records) == 1


def test_a_corrupt_entry_propagates_out_of_render_level(box_template: Path):
    spy = SpyBackend()
    previous = current_settings()
    configure_pyjinhx(previous.merge(cache_backend=spy))
    try:
        key = render_cache_key(_CachedBox(id="a", label="hi"))
        spy.put(key, "not a level", tags=(), ttl=None)
        with pytest.raises(ValueError, match="not a RenderedLevel"):
            render_level(_CachedBox(id="a", label="hi"), RenderSession())
    finally:
        configure_pyjinhx(previous)
