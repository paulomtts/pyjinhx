"""PjxContext is a live view: every accessor re-reads session.py, nothing caches."""

import pytest

from pyjinhx2.context import PjxContext
from pyjinhx2.session import (
    NoActiveRequestScope,
    add_dirtied,
    current_session,
    get_cache_reverse,
    get_cache_store,
    get_dirtied,
    get_instances,
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
