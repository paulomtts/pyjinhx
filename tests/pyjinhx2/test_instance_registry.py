"""Tests for the minimal request-scoped instance registry (ADR 0009)."""

import pytest

from pyjinhx2.registry import make_key, resolve
from pyjinhx2.segments import RenderedLevel
from pyjinhx2.session import _instances, get_instances, request_scope


def test_make_key_joins_type_and_id_with_underscore():
    assert make_key("PJXButton", "btn1") == "PJXButton_btn1"
    assert make_key("Card", "42") == "Card_42"
    assert make_key("", "") == "_"


class Widget:
    """Stand-in for a live component instance."""

    def __init__(self, label: str):
        self.label = label


def test_resolve_returns_the_stored_live_instance():
    widget = Widget("hello")
    with request_scope():
        get_instances()[make_key("Widget", "w1")] = widget
        assert resolve("Widget", "w1") is widget


def test_resolve_returns_cached_rendered_level_with_root_span_intact():
    level = RenderedLevel(segments=["<div>hi</div>"], root_span=(0, 5), descriptor=None)
    with request_scope():
        get_instances()[make_key("Card", "c1")] = level
        resolved = resolve("Card", "c1")
    assert resolved is level
    assert isinstance(resolved, RenderedLevel)
    assert resolved.root_span == (0, 5)
    assert resolved.segments == ["<div>hi</div>"]


def test_resolve_unknown_key_raises_lookup_error_naming_the_key():
    with request_scope(), pytest.raises(LookupError, match="Widget_missing"):
        resolve("Widget", "missing")


def test_resolve_outside_request_scope_always_raises():
    assert _instances.get() is None
    with pytest.raises(LookupError, match="Widget_w1"):
        resolve("Widget", "w1")


def test_resolve_with_empty_names_is_an_ordinary_miss():
    with request_scope(), pytest.raises(LookupError):
        resolve("", "")


def test_key_from_a_previous_scope_does_not_survive_the_reset():
    widget = Widget("old")
    with request_scope():
        get_instances()[make_key("Widget", "w1")] = widget
        assert resolve("Widget", "w1") is widget
    with request_scope(), pytest.raises(LookupError, match="Widget_w1"):
        resolve("Widget", "w1")


def test_two_requests_reusing_one_key_each_see_only_their_own_entry():
    first = Widget("first")
    second = Widget("second")
    with request_scope():
        get_instances()[make_key("Widget", "w1")] = first
        assert resolve("Widget", "w1") is first
    with request_scope():
        get_instances()[make_key("Widget", "w1")] = second
        assert resolve("Widget", "w1") is second


def test_entry_removed_mid_scope_raises_instead_of_returning_stale_data():
    # Stands in for the invalidation #435's writer will perform: once the entry
    # is gone, resolve must miss rather than hand back what it saw a moment ago.
    widget = Widget("doomed")
    with request_scope():
        instances = get_instances()
        instances[make_key("Widget", "w1")] = widget
        assert resolve("Widget", "w1") is widget
        del instances[make_key("Widget", "w1")]
        with pytest.raises(LookupError, match="Widget_w1"):
            resolve("Widget", "w1")
