"""Fixtures shared by the split test files in this folder."""

import dataclasses

import pytest

from pyjinhx.components import discovery
from tests.unit.reactive.fanout._helpers import (
    BOOM_KEYS,
    CHILD_REGISTERED,
    GONE_KEYS,
    LOAD_CALLS,
    RENDERS,
    SEEN_LOAD_CONTEXTS,
    SEEN_SESSIONS,
    SEEN_THREADS,
    STAT_CALLS,
    FanoutWidget,
    HollowHostWidget,
    HostWidget,
    LoudWidget,
    MiddleWidget,
    NestedChildWidget,
    NestingParentWidget,
    OuterWidget,
    OwnedWidget,
    PlainWidget,
    PreservingHostWidget,
    QuietWidget,
    SpyWidget,
)


@pytest.fixture(autouse=True)
def _clean_registries(tmp_path, monkeypatch):
    """Publish a tag -> class map for the two test classes and reset call spies."""
    LOAD_CALLS.clear()
    GONE_KEYS.clear()
    SEEN_SESSIONS.clear()
    SEEN_LOAD_CONTEXTS.clear()
    SEEN_THREADS.clear()
    STAT_CALLS.clear()
    RENDERS.clear()
    BOOM_KEYS.clear()
    spy_path = tmp_path / "spy_widget.pjx"
    spy_path.write_text("<div>{{ pjx_key }}</div>")
    fanout_path = tmp_path / "fanout_widget.pjx"
    quiet_path = tmp_path / "quiet_widget.pjx"
    fanout_path.write_text("<div>{{ pjx_key }}</div>")
    quiet_path.write_text("<div>quiet</div>")
    owned_path = tmp_path / "owned_widget.pjx"
    owned_path.write_text("<div>owned</div>")
    plain_path = tmp_path / "plain_widget.pjx"
    plain_path.write_text("<div>plain</div>")
    loud_path = tmp_path / "loud_widget.pjx"
    loud_path.write_text("<div>{{ pjx_key }}</div>")
    CHILD_REGISTERED.clear()
    child_path = tmp_path / "nested_child_widget.pjx"
    child_path.write_text("<div>child {{ pjx_key }}</div>")
    parent_path = tmp_path / "nesting_parent_widget.pjx"
    parent_path.write_text(
        '<div>parent <NestedChildWidget pjx_key="k1" id="child-1" /></div>'
    )
    host_path = tmp_path / "host_widget.pjx"
    host_path.write_text(
        '<div>host <NestedChildWidget pjx_key="k1" id="child-1" /></div>'
    )
    hollow_path = tmp_path / "hollow_host_widget.pjx"
    hollow_path.write_text("<div>hollow</div>")
    outer_path = tmp_path / "outer_widget.pjx"
    outer_path.write_text(
        '<div>outer <MiddleWidget pjx_key="k1" id="middle-1" /></div>'
    )
    middle_path = tmp_path / "middle_widget.pjx"
    middle_path.write_text(
        '<div>middle <NestedChildWidget pjx_key="k1" id="child-1" /></div>'
    )
    phost_path = tmp_path / "preserving_host_widget.pjx"
    phost_path.write_text(
        '<div><NestedChildWidget pjx_key="k1" id="child-1" />'
        '<QuietWidget id="quiet-1" /></div>'
    )
    discovery.build_registry(
        tmp_path,
        [
            FanoutWidget,
            QuietWidget,
            PlainWidget,
            SpyWidget,
            LoudWidget,
            OwnedWidget,
            NestedChildWidget,
            NestingParentWidget,
            HostWidget,
            HollowHostWidget,
            OuterWidget,
            MiddleWidget,
            PreservingHostWidget,
        ],
    )
    # `_resolve_template_path` walks the class's *defining module's* directory
    # (this test file's dir), not `template_dir` passed to `build_registry` —
    # the two are deliberately different concerns (tag lookup vs. file probe).
    # Point each descriptor's `template_path` at this test's tmp_path file, the
    # same way tests/unit/rendering/pipeline/test_integration.py does, so render_level()
    # finds a real file instead of falling back to an ancestor's unprobed guess.
    # The loader is absolute-only, so each descriptor carries the full path.
    PlainWidget.__pjx_descriptor__ = dataclasses.replace(
        PlainWidget.__pjx_descriptor__, template_path=plain_path
    )
    FanoutWidget.__pjx_descriptor__ = dataclasses.replace(
        FanoutWidget.__pjx_descriptor__, template_path=fanout_path
    )
    QuietWidget.__pjx_descriptor__ = dataclasses.replace(
        QuietWidget.__pjx_descriptor__, template_path=quiet_path
    )
    SpyWidget.__pjx_descriptor__ = dataclasses.replace(
        SpyWidget.__pjx_descriptor__, template_path=spy_path
    )
    LoudWidget.__pjx_descriptor__ = dataclasses.replace(
        LoudWidget.__pjx_descriptor__, template_path=loud_path
    )
    OwnedWidget.__pjx_descriptor__ = dataclasses.replace(
        OwnedWidget.__pjx_descriptor__, template_path=owned_path
    )
    NestedChildWidget.__pjx_descriptor__ = dataclasses.replace(
        NestedChildWidget.__pjx_descriptor__, template_path=child_path
    )
    NestingParentWidget.__pjx_descriptor__ = dataclasses.replace(
        NestingParentWidget.__pjx_descriptor__, template_path=parent_path
    )
    HostWidget.__pjx_descriptor__ = dataclasses.replace(
        HostWidget.__pjx_descriptor__, template_path=host_path
    )
    HollowHostWidget.__pjx_descriptor__ = dataclasses.replace(
        HollowHostWidget.__pjx_descriptor__, template_path=hollow_path
    )
    OuterWidget.__pjx_descriptor__ = dataclasses.replace(
        OuterWidget.__pjx_descriptor__, template_path=outer_path
    )
    MiddleWidget.__pjx_descriptor__ = dataclasses.replace(
        MiddleWidget.__pjx_descriptor__, template_path=middle_path
    )
    PreservingHostWidget.__pjx_descriptor__ = dataclasses.replace(
        PreservingHostWidget.__pjx_descriptor__, template_path=phost_path
    )
    yield
