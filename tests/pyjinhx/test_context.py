"""PjxContext is a live view: every accessor re-reads session.py, nothing caches."""

import pytest

from pyjinhx.context import PjxContext
from pyjinhx.session import (
    NoActiveRequestScope,
    add_dirtied,
    current_session,
    get_cache_reverse,
    get_cache_store,
    get_dirtied,
    get_instances,
    get_load_context,
    request_scope,
)


class FakeState:
    """Stand-in for ``request.state``, populated the way PjxScopeMiddleware does."""

    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)


class FakeRequest:
    """Stand-in for a Starlette Request carrying only the pjx state attributes."""

    def __init__(self, **values: object) -> None:
        self.state = FakeState(**values)


def test_session_accessor_is_the_bound_session():
    with request_scope() as session:
        assert PjxContext.current().session is session


def test_dirtied_instances_and_cache_accessors_are_identity_stable():
    with request_scope():
        ctx = PjxContext.current()
        assert ctx.dirtied is get_dirtied()
        assert ctx.instances is get_instances()
        assert ctx.cache_store is get_cache_store()
        assert ctx.cache_reverse is get_cache_reverse()


def test_dirtied_reflects_later_mutations_without_staleness():
    with request_scope():
        ctx = PjxContext.current()
        add_dirtied(["Widget:1"])
        assert "Widget:1" in ctx.dirtied
        assert ctx.dirtied is get_dirtied()


def test_current_outside_a_request_scope_raises_no_active_request_scope():
    assert current_session() is None
    with pytest.raises(NoActiveRequestScope):
        PjxContext.current()


def test_manifest_accessors_read_request_state():
    request = FakeRequest(
        pjx_mounted="mounted-manifest",
        pjx_assets="loaded-assets",
        pjx_trigger="trigger-manifest",
    )
    with request_scope() as session:
        session.pjx_request = request
        ctx = PjxContext.current()
        assert ctx.request is request
        assert ctx.mounted == "mounted-manifest"
        assert ctx.assets == "loaded-assets"
        assert ctx.trigger == "trigger-manifest"


def test_manifest_accessors_are_none_without_a_request():
    with request_scope():
        ctx = PjxContext.current()
        assert ctx.request is None
        assert ctx.mounted is None
        assert ctx.assets is None
        assert ctx.trigger is None


def test_app_context_is_none_when_no_load_context_was_bound():
    with request_scope():
        assert PjxContext.current().app_context is None


def test_app_context_is_the_bound_load_context():
    sentinel = object()
    with request_scope(load_context=sentinel):
        assert PjxContext.current().app_context is sentinel


def test_app_context_does_not_need_a_request():
    """The value rides the ContextVar, so a scope entered without a Starlette
    request - a test, a script, a background task - still reads it."""
    sentinel = object()
    with request_scope(load_context=sentinel) as session:
        assert getattr(session, "pjx_request", None) is None
        assert PjxContext.current().app_context is sentinel


def test_app_context_is_none_with_no_active_scope():
    assert PjxContext(request=None).app_context is None


def test_app_context_is_the_same_object_the_session_accessor_returns():
    sentinel = object()
    with request_scope(load_context=sentinel):
        assert PjxContext.current().app_context is get_load_context()
