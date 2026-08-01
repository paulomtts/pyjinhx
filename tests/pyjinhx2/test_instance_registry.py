"""Tests for the minimal request-scoped instance registry (ADR 0009)."""

import logging
from pathlib import Path

import pytest

from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.reactive.component import ReactiveComponent
from pyjinhx2.registry import (
    make_key,
    register_instance,
    register_rendered_instance,
    resolve,
)
from pyjinhx2.render import render_level
from pyjinhx2.segments import RenderedLevel, serialize
from pyjinhx2.session import RenderSession, _instances, get_instances, request_scope


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


def test_register_instance_makes_the_entry_resolvable():
    widget = Widget("written")
    with request_scope():
        register_instance("Widget", "w1", widget)
        assert resolve("Widget", "w1") is widget


def test_register_instance_stores_under_the_composite_key():
    widget = Widget("written")
    with request_scope():
        register_instance("Widget", "w1", widget)
        assert get_instances()["Widget_w1"] is widget


def test_register_instance_accepts_a_cached_rendered_level():
    level = RenderedLevel(segments=["<div>hi</div>"], root_span=(0, 5), descriptor=None)
    with request_scope():
        register_instance("Card", "c1", level)
        resolved = resolve("Card", "c1")
    assert resolved is level
    assert isinstance(resolved, RenderedLevel)
    assert resolved.root_span == (0, 5)


def test_register_instance_duplicate_key_overwrites_last_write_wins():
    first = Widget("first")
    second = Widget("second")
    with request_scope():
        register_instance("Widget", "w1", first)
        register_instance("Widget", "w1", second)
        assert resolve("Widget", "w1") is second


def test_register_instance_duplicate_key_warns_naming_the_key(caplog):
    with request_scope(), caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        register_instance("Widget", "w1", Widget("first"))
        assert caplog.records == []
        register_instance("Widget", "w1", Widget("second"))
    assert len(caplog.records) == 1
    assert "Widget_w1" in caplog.records[0].getMessage()


def test_register_instance_outside_request_scope_is_a_logged_no_op(caplog):
    assert _instances.get() is None
    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        register_instance("Widget", "w1", Widget("orphan"))
    assert len(caplog.records) == 1
    assert "Widget_w1" in caplog.records[0].getMessage()
    with pytest.raises(LookupError, match="Widget_w1"):
        resolve("Widget", "w1")


def test_registered_entry_does_not_survive_the_scope_reset():
    with request_scope():
        register_instance("Widget", "w1", Widget("old"))
        assert resolve("Widget", "w1") is not None
    with request_scope(), pytest.raises(LookupError, match="Widget_w1"):
        resolve("Widget", "w1")


def test_registered_then_removed_entry_raises_instead_of_returning_stale_data():
    with request_scope():
        register_instance("Widget", "w1", Widget("doomed"))
        del get_instances()[make_key("Widget", "w1")]
        with pytest.raises(LookupError, match="Widget_w1"):
            resolve("Widget", "w1")


class FakeComponent:
    """Stand-in with the two attributes the subscriber reads off a component."""

    def __init__(self, id: str):
        self.id = id


def test_register_rendered_instance_stores_the_level_under_type_and_id():
    level = RenderedLevel(segments=["<p>x</p>"], root_span=(0, 3), descriptor=None)
    component = FakeComponent("f1")
    session = RenderSession()
    with request_scope(session=session):
        register_rendered_instance(component, level, session)
        assert resolve("FakeComponent", "f1") is level


def test_render_session_does_not_subscribe_the_registry_writer_by_default():
    session = RenderSession()
    assert register_rendered_instance not in session.on_rendered


def test_emit_rendered_registers_nothing_until_the_writer_is_subscribed():
    level = RenderedLevel(segments=["<p>x</p>"], root_span=(0, 3), descriptor=None)
    component = FakeComponent("f1")
    session = RenderSession()
    with request_scope(session=session):
        session.emit_rendered(component, level)  # type: ignore[arg-type]
        assert get_instances() == {}
        session.on_rendered.append(register_rendered_instance)
        session.emit_rendered(component, level)  # type: ignore[arg-type]
        assert resolve("FakeComponent", "f1") is level


class RegisteredWidget(ReactiveComponent):
    """A real component rendered through the real pipeline for these tests."""


RegisteredWidget.__pjx_descriptor__ = ClassDescriptor(
    template_path=Path("reactive_widget.html"),
    slot_fields=frozenset(),
    children_field=None,
    css_paths=(),
    js_paths=(),
    strict=True,
    provenance={"template": RegisteredWidget},
)


def _wired_session() -> RenderSession:
    """A session whose on_rendered carries the registry writer, as the Load path wires it."""
    session = RenderSession(template_dir="tests/templates")
    session.on_rendered.append(register_rendered_instance)
    return session


def test_real_render_with_the_writer_subscribed_registers_a_resolvable_entry():
    session = _wired_session()
    component = RegisteredWidget(id="r1")

    with request_scope(session=session):
        level = render_level(component, session)
        assert resolve("RegisteredWidget", "r1") is level


def test_the_registered_entry_is_the_rendered_level_not_a_copy():
    session = _wired_session()
    component = RegisteredWidget(id="r2")

    with request_scope(session=session):
        level = render_level(component, session)
        resolved = resolve("RegisteredWidget", "r2")
        assert isinstance(resolved, RenderedLevel)
        assert serialize(resolved) == serialize(level)


def test_the_real_render_stores_under_the_composite_key():
    session = _wired_session()

    with request_scope(session=session):
        render_level(RegisteredWidget(id="r3"), session)
        assert make_key("RegisteredWidget", "r3") in get_instances()


def test_a_real_render_entry_does_not_survive_the_request_scope():
    session = _wired_session()

    with request_scope(session=session):
        render_level(RegisteredWidget(id="r4"), session)
        assert resolve("RegisteredWidget", "r4") is not None

    with pytest.raises(LookupError, match="RegisteredWidget_r4"):
        resolve("RegisteredWidget", "r4")


def test_a_real_render_registers_nothing_when_the_writer_is_not_wired():
    session = RenderSession(template_dir="tests/templates")

    with request_scope(session=session):
        render_level(RegisteredWidget(id="r5"), session)
        assert get_instances() == {}
        with pytest.raises(LookupError, match="RegisteredWidget_r5"):
            resolve("RegisteredWidget", "r5")


def test_two_instances_of_one_class_register_under_their_own_ids():
    session = _wired_session()

    with request_scope(session=session):
        first = render_level(RegisteredWidget(id="r6"), session)
        second = render_level(RegisteredWidget(id="r7"), session)
        assert resolve("RegisteredWidget", "r6") is first
        assert resolve("RegisteredWidget", "r7") is second
