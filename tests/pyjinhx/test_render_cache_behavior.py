"""What the non-reactive render cache promises a caller, exercised through whole
component trees on the real render path.

The unit-level halves live elsewhere: test_render_cache_key.py owns key
derivation, test_render_cache_store.py the store/restore round trip, and
test_render_cache_wiring.py the render_level() call pattern — that the backend
is consulted, that it stops being consulted when told to, and how a degraded or
corrupt entry is handled. What is pinned here is the user-visible behavior one
layer up: markup that stays correct across a hit, an edited template that
actually reaches the page, assets that survive a hit, and the boundary that
keeps reactive components off this cache entirely.
"""

import os
from pathlib import Path
from typing import Annotated

import pytest

from pyjinhx import discovery, rendering
from pyjinhx._component import BaseComponent, _pascal_to_snake
from pyjinhx.assets import asset_token
from pyjinhx.config import configure_pyjinhx, current_settings
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.reactive.backend import InMemoryCacheBackend
from pyjinhx.reactive.backend_health import reset_backend_health
from pyjinhx.reactive.component import PjxKey, ReactiveComponent, _string_cache_key
from pyjinhx.render_cache import render_cache_key
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession, accumulate_assets, request_scope


class SpyBackend(InMemoryCacheBackend):
    """An in-memory backend that records the keys it was asked for.

    A local twin of test_render_cache_wiring.py's SpyBackend rather than an
    import across test modules: that one also carries fail_get/fail_put for the
    degradation tests this module deliberately does not repeat, and neither
    file should own the other's fixture.
    """

    def __init__(self) -> None:
        super().__init__()
        self.gets: list[str] = []
        self.puts: list[str] = []

    def get(self, key: str) -> object:
        self.gets.append(key)
        return super().get(key)

    def put(self, key: str, value: object, *, tags, ttl) -> None:
        self.puts.append(key)
        super().put(key, value, tags=tags, ttl=ttl)


@pytest.fixture
def spy():
    """Publish a fresh recording backend for one test, then restore the settings.

    configure_pyjinhx rather than shutdown_pyjinhx, matching
    reactive/test_reactive_cache_tier2_wiring.py: a test that asked for a
    backend should not also blow away whatever else the process was configured
    with.
    """
    previous = current_settings()
    published = SpyBackend()
    configure_pyjinhx(previous.merge(cache_backend=published))
    yield published
    configure_pyjinhx(previous)


@pytest.fixture(autouse=True)
def clean_health():
    """Backend health is process-wide: no test may inherit another's flags."""
    reset_backend_health()
    yield
    reset_backend_health()


@pytest.fixture(autouse=True)
def reset_registry():
    """The tag registry is process-wide: no test may inherit another's mapping."""
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    yield
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def _attach(
    cls: type[BaseComponent],
    template_path: Path,
    *,
    slot_fields: frozenset[str] = frozenset(),
    children_field: str | None = None,
    css_paths: tuple[Path, ...] = (),
    js_paths: tuple[Path, ...] = (),
) -> None:
    """Point a class at a tmp-path template, as the sibling cache tests do."""
    cls.__pjx_descriptor__ = ClassDescriptor(
        template_path=template_path,
        slot_fields=slot_fields,
        children_field=children_field,
        css_paths=css_paths,
        js_paths=js_paths,
        strict=True,
        provenance={"template": cls},
    )


class _Shell(BaseComponent):
    label: str = "shell"


class _AlphaChild(BaseComponent):
    pass


class _BetaChild(BaseComponent):
    pass


def test_hit_with_different_children_splices_correctly(spy: SpyBackend, tmp_path: Path):
    """A cached shell keeps its holes: the second render hits the same entry and
    still renders whichever child the registry resolves this time.

    Not a Slot/Children field holding a component — that shape is refused by the
    cache outright (holds_spliced_components), and its refusal is
    test_render_cache_wiring.py's. The cacheable shape that carries a real
    unresolved ChildRef is a child tag in the shell's own template, resolved per
    request, which is what swapping the registry entry between the two renders
    exercises.
    """
    alpha = tmp_path / "alpha.html"
    alpha.write_text("<span>alpha</span>", encoding="utf-8")
    _attach(_AlphaChild, alpha)
    beta = tmp_path / "beta.html"
    beta.write_text("<span>beta</span>", encoding="utf-8")
    _attach(_BetaChild, beta)
    shell = tmp_path / "shell.html"
    shell.write_text('<div class="shell">{{ label }}<Inner/></div>', encoding="utf-8")
    _attach(_Shell, shell)
    shell_key = render_cache_key(_Shell(id="s"))

    discovery._registry.mapping = {_pascal_to_snake("Inner"): _AlphaChild}
    first = render(_Shell(id="s"), RenderSession())
    discovery._registry.mapping = {_pascal_to_snake("Inner"): _BetaChild}
    second = render(_Shell(id="s"), RenderSession())

    assert first == '<div class="shell">shell<span>alpha</span></div>'
    assert second == '<div class="shell">shell<span>beta</span></div>'
    # One write, two reads: the second render answered from the entry the first
    # one stored rather than re-parsing the shell template.
    assert spy.puts.count(shell_key) == 1
    assert spy.gets.count(shell_key) == 2


class _EditableBox(BaseComponent):
    label: str = "hi"


def test_template_edit_busts_cache_key(spy: SpyBackend, tmp_path: Path):
    """An author editing a template is seen by the next render, not swallowed.

    The mtime the key carries is the only thing standing between an edit and a
    page served from an entry no restart would clear, so the assertion is on the
    markup that reaches the caller and on the two distinct keys behind it.
    """
    template = tmp_path / "editable.html"
    template.write_text("<div>v1 {{ label }}</div>", encoding="utf-8")
    _attach(_EditableBox, template)

    first = render(_EditableBox(id="b"), RenderSession())
    # An explicit bump rather than trusting two writes to land on different
    # clock ticks: a filesystem with coarse mtime granularity would otherwise
    # make this test flaky rather than meaningful.
    bumped = template.stat().st_mtime + 10
    template.write_text("<div>v2 {{ label }}</div>", encoding="utf-8")
    os.utime(template, (bumped, bumped))
    second = render(_EditableBox(id="b"), RenderSession())

    assert first == "<div>v1 hi</div>"
    assert second == "<div>v2 hi</div>"
    # Two writes under two different keys: the edit produced a new entry rather
    # than overwriting or hitting the old one.
    assert len(spy.puts) == 2
    assert spy.puts[0] != spy.puts[1]


class _AssetShell(BaseComponent):
    pass


def _accumulating_session() -> RenderSession:
    """A fresh session wired the way the live asset path is.

    accumulate_assets is opt-in per session (see tests/pyjinhx/test_assets.py):
    a bare RenderSession() emits nothing on a live render either, so a session
    that never subscribed proves nothing about a hit.
    """
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    return session


def test_hit_still_emits_css_and_js(spy: SpyBackend, tmp_path: Path):
    """Assets are part of the response, so a hit has to deliver them too.

    Asserted on the markup render() actually returns — in the default INLINE
    mode emit_assets reads each accumulated file and inlines its text — rather
    than on the accumulator sets, because what a page is missing when the replay
    does not fire is the tag, not a set entry. Both levels of the tree carry
    assets: the shell answers from the cache and the child renders through it.
    """
    shell_css = tmp_path / "shell.css"
    shell_css.write_text(".shell{color:SHELLCSS}", encoding="utf-8")
    shell_js = tmp_path / "shell.js"
    shell_js.write_text("window.SHELLJS=1", encoding="utf-8")
    child_css = tmp_path / "child.css"
    child_css.write_text(".child{color:CHILDCSS}", encoding="utf-8")
    child_js = tmp_path / "child.js"
    child_js.write_text("window.CHILDJS=1", encoding="utf-8")

    child_template = tmp_path / "asset_child.html"
    child_template.write_text("<span>child</span>", encoding="utf-8")
    _attach(_AlphaChild, child_template, css_paths=(child_css,), js_paths=(child_js,))
    shell_template = tmp_path / "asset_shell.html"
    shell_template.write_text("<div><Inner/></div>", encoding="utf-8")
    _attach(_AssetShell, shell_template, css_paths=(shell_css,), js_paths=(shell_js,))
    discovery._registry.mapping = {_pascal_to_snake("Inner"): _AlphaChild}
    shell_key = render_cache_key(_AssetShell(id="a"))

    cold = render(_AssetShell(id="a"), _accumulating_session())
    warm = render(_AssetShell(id="a"), _accumulating_session())

    assert "SHELLCSS" in cold
    assert "SHELLJS" in cold
    assert warm == cold
    shell_token = asset_token(shell_css)
    child_token = asset_token(child_css)
    assert (
        f'<style data-pjx-asset="{shell_token}">.shell{{color:SHELLCSS}}</style>'
        in warm
    )
    assert "<script>window.SHELLJS=1</script>" in warm
    assert (
        f'<style data-pjx-asset="{child_token}">.child{{color:CHILDCSS}}</style>'
        in warm
    )
    assert "<script>window.CHILDJS=1</script>" in warm
    # The second render really was a hit, so the assertions above are about the
    # replay rather than about a second live render.
    assert spy.puts.count(shell_key) == 1
    assert spy.gets.count(shell_key) == 2


class _OptedOut(BaseComponent, cache=False):
    label: str = "hi"


def test_cache_false_never_touches_backend(spy: SpyBackend, tmp_path: Path):
    """cache=False is a promise about the whole request, not just resolution.

    The wiring module already pins that render_level() skips the backend for
    such a class; what this adds is the end-to-end answer — two full render()
    calls, a configured backend that records everything, and markup that matches
    the same tree rendered with tier 2 turned off entirely.
    """
    child = tmp_path / "opted_child.html"
    child.write_text("<span>child</span>", encoding="utf-8")
    _attach(_AlphaChild, child)
    template = tmp_path / "opted_out.html"
    template.write_text("<div>{{ label }}<Inner/></div>", encoding="utf-8")
    _attach(_OptedOut, template)
    discovery._registry.mapping = {_pascal_to_snake("Inner"): _AlphaChild}

    first = render(_OptedOut(id="o"), RenderSession())
    second = render(_OptedOut(id="o"), RenderSession())

    assert first == second == "<div>hi<span>child</span></div>"
    # The child is an ordinary cacheable class and legitimately uses the
    # backend; nothing keyed for the opted-out parent may appear.
    parent_keys = [key for key in spy.gets + spy.puts if "_OptedOut" in key]
    assert parent_keys == []


def test_no_backend_configured_matches_configured_behavior(tmp_path: Path):
    """Tier 2 is invisible: the same tree renders identically with and without it.

    Both configurations render twice, so a cache that changed the second render
    of a tree — the failure mode a single render would not catch — shows up as a
    difference against the uncached baseline rather than as four equal strings.
    """
    child = tmp_path / "parity_child.html"
    child.write_text("<span>child</span>", encoding="utf-8")
    _attach(_AlphaChild, child)
    shell = tmp_path / "parity_shell.html"
    shell.write_text('<div class="shell">{{ label }}<Inner/></div>', encoding="utf-8")
    _attach(_Shell, shell)
    discovery._registry.mapping = {_pascal_to_snake("Inner"): _AlphaChild}

    previous = current_settings()
    configure_pyjinhx(previous.merge(cache_backend=None))
    try:
        cold_off = render(_Shell(id="s"), RenderSession())
        warm_off = render(_Shell(id="s"), RenderSession())
    finally:
        configure_pyjinhx(previous)

    configure_pyjinhx(previous.merge(cache_backend=SpyBackend()))
    try:
        cold_on = render(_Shell(id="s"), RenderSession())
        warm_on = render(_Shell(id="s"), RenderSession())
    finally:
        configure_pyjinhx(previous)

    assert cold_off == '<div class="shell">shell<span>child</span></div>'
    assert warm_off == cold_off
    assert cold_on == cold_off
    assert warm_on == cold_off


_load_calls: list[int] = []


class _CachedRow(ReactiveComponent):
    row_id: Annotated[int, PjxKey()] = 0
    label: str = ""

    @classmethod
    def load(cls, row_id: int) -> "_CachedRow":
        _load_calls.append(row_id)
        return cls(row_id=row_id, label=f"row {row_id}")


def test_reactive_component_never_uses_render_cache(
    spy: SpyBackend, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A reactive class caches its load() result and nothing else.

    Two independently invalidated stores holding one component is the failure
    this boundary exists to prevent: the load cache is evicted by reactive keys,
    the render cache only by ttl and template mtime, so a render-cached shell
    would outlive the data it was rendered from. The marker _pjx_key_field is
    what takes the level off the render-cache path, so the assertion is that no
    render key is ever derived for this class — while its own two-tier load
    cache goes on working exactly as it does without a render cache in the
    picture.
    """
    _load_calls.clear()
    template = tmp_path / "row.html"
    template.write_text("<div>{{ label }}</div>", encoding="utf-8")
    _attach(_CachedRow, template)

    real_render_cache_key = rendering.render_cache_key

    def guarded(component: BaseComponent) -> str:
        if isinstance(component, ReactiveComponent):
            raise AssertionError(  # noqa: TRY004
                "a reactive component must never be render-cached"
            )
        return real_render_cache_key(component)

    monkeypatch.setattr(rendering, "render_cache_key", guarded)

    with request_scope():
        first = render(_CachedRow(id="r", row_id=7), RenderSession())
    # A second request: tier 1 is gone with the scope, so only the load cache's
    # tier 2 can spare the real load() call.
    with request_scope():
        second = render(_CachedRow(id="r", row_id=7), RenderSession())

    assert first == second == "<div>row 7</div>"
    assert _load_calls == [7]
    # The only key this class put through the backend is its load key: no render
    # key was written beside it.
    load_key = _string_cache_key(_CachedRow, {"row_id": 7}, protocol_mode=False)
    assert spy.puts == [load_key]
    assert set(spy.gets) == {load_key}
