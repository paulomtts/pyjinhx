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
