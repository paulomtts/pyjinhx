"""Regression for https://github.com/paulomtts/pyjinhx/issues/222.

``build_render_context`` used to iterate every registered instance on every
single node render, so a page with N registered components did O(N) work per
node -- O(N^2) total. The fix caches the registry-derived defaults on the
render session and only folds in instances registered since the last node
rendered, so the total work across a whole render pass is O(N) instead of
O(N^2).

As of #240 the cache is no longer materialized into the returned context at
all -- ``_PjxContext`` (renderer.py) resolves peers by name straight out of
``session.registry_defaults`` -- so these tests assert on the cache itself.
"""

from pyjinhx import Registry
from pyjinhx.assets import RenderSession
from pyjinhx.renderer import build_render_context
from tests.ui.unified_component import UnifiedComponent


def test_build_render_context_scans_registry_incrementally():
    Registry.clear_instances()
    session = RenderSession()

    total_folded = 0
    with Registry.request_scope():
        for i in range(20):
            UnifiedComponent(id=f"scan-{i}", text=str(i))
            before = len(session.registry_defaults)
            build_render_context({}, session)
            total_folded += len(session.registry_defaults) - before

        # Every instance is folded into the cache exactly once across the
        # whole render pass -- not re-visited on every subsequent node.
        assert total_folded == 20
        assert session.registry_scanned == 20
        assert len(session.registry_defaults) == 20


def test_build_render_context_contents_match_registry_and_context_wins():
    Registry.clear_instances()
    session = RenderSession()

    with Registry.request_scope():
        first = UnifiedComponent(id="peer-a", text="a")
        build_render_context({}, session)
        assert session.registry_defaults["peer-a"] is first

        second = UnifiedComponent(id="peer-b", text="b")
        build_render_context({}, session)
        assert session.registry_defaults["peer-a"] is first
        assert session.registry_defaults["peer-b"] is second

        # Peers stay out of the returned context entirely -- they are resolved
        # lazily by name, and a per-node value with the same name still wins
        # because the lazy lookup only runs after normal resolution misses.
        override = UnifiedComponent(id="override-noop", text="override")
        render_context = build_render_context({"peer-b": "explicit"}, session)
        assert render_context == {"peer-b": "explicit"}
        assert session.registry_defaults["override-noop"] is override


def test_build_render_context_repeat_calls_dont_rescan_unchanged_registry():
    Registry.clear_instances()
    session = RenderSession()

    with Registry.request_scope():
        UnifiedComponent(id="stable-1", text="x")
        build_render_context({}, session)
        scanned_after_first_call = session.registry_scanned

        # No new registrations happened; a repeat call must not re-derive
        # the cache from scratch (registry_scanned stays put).
        build_render_context({}, session)
        assert session.registry_scanned == scanned_after_first_call == 1
