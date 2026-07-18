from pathlib import Path
from typing import Annotated

import pytest

from pyjinhx import MutationKey, PjxKey, ReactiveComponent, Registry, Renderer
from pyjinhx.cache import LoadCache
from pyjinhx.dev import disable_reactive_dev, enable_reactive_dev
from pyjinhx.reactive import oob_swaps
from tests.ui.reactive.conditional_panel import ConditionalPanel  # noqa: F401
from tests.ui.reactive.dynamic_widget import DynamicWidget
from tests.ui.reactive.store import state

UI_ROOT = Path(__file__).parent.parent / "ui" / "reactive"


class _Keys(MutationKey):
    ALPHA = "alpha"


class OverBroad(ReactiveComponent, react={_Keys.ALPHA}):
    @classmethod
    def load(cls) -> "OverBroad":
        return cls(id="over")

    def depends_on(self) -> set[str]:
        return {"alpha", "extra"}


class KeyedProbe(ReactiveComponent, react={_Keys.ALPHA}):
    probe_key: Annotated[str, PjxKey()]

    @classmethod
    def load(cls, key: str) -> "KeyedProbe":
        return cls(id=f"probe-{key}", probe_key=key)


def setup_function():
    LoadCache.clear()
    state["dynamic_narrow"] = True
    disable_reactive_dev()


def teardown_function():
    disable_reactive_dev()


def test_oob_skips_when_static_reacts_to_does_not_intersect_dirtied():
    manifest = [
        {
            "id": "panel",
            "type": "ConditionalPanel",
            "hash": "stale",
        }
    ]
    out = str(oob_swaps({"todos"}, manifest))
    assert "outerHTML:[data-pjx-id='panel']" not in out


def test_oob_swaps_when_static_reacts_to_intersects_dirtied():
    prev = Renderer.peek_default_environment()
    Renderer.set_default_environment(UI_ROOT)
    try:
        manifest = [
            {
                "id": "panel",
                "type": "ConditionalPanel",
                "hash": "stale",
            }
        ]
        out = str(oob_swaps({"settings"}, manifest))
        assert "outerHTML:[data-pjx-id='panel']" in out
    finally:
        Renderer.set_default_environment(prev)


def test_cache_reindex_tracks_runtime_keys():
    DynamicWidget.load()
    LoadCache.invalidate({"beta"})
    assert DynamicWidget.load().flag == "on"

    state["dynamic_narrow"] = False
    LoadCache.invalidate({"alpha"})
    DynamicWidget.load()
    LoadCache.invalidate({"beta"})
    with Registry.request_scope():
        reloaded = DynamicWidget.load()
    assert reloaded.flag == "off"


def test_depends_on_exceeding_superset_raises_in_strict_dev():
    enable_reactive_dev(strict=True)
    with pytest.raises(RuntimeError, match="depends_on"):
        OverBroad.load()


def test_keyed_component_default_depends_on_includes_derived_key():
    instance = KeyedProbe.load("7")
    assert instance.depends_on() == {"alpha", "alpha:7"}


def test_keyed_component_default_depends_on_does_not_trip_strict_dev():
    enable_reactive_dev(strict=True)
    KeyedProbe.load("9")  # must not raise — the derived key is expected, not "extra"
