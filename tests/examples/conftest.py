"""Shared fixtures for the todo example's component tests.

Every test runs inside its own request_scope: load() results are memoized per
request, so a shared scope would let one test's cached load leak into the next.
"""

import pytest

from examples.todo import store as todo_store
from examples.todo.context import TodoAppContext
from pyjinhx.assets import AssetMode
from pyjinhx.session import RenderSession, accumulate_assets, request_scope


@pytest.fixture(autouse=True)
def fresh_store():
    """Reset the demo store to its three seeded todos around every test."""
    todo_store.reset()
    yield
    todo_store.reset()


@pytest.fixture
def ctx():
    """The per-request context the todo app's context_factory would return."""
    return TodoAppContext(store=todo_store)


@pytest.fixture
def session():
    """A RenderSession that inlines co-located component CSS, as a real page does."""
    render_session = RenderSession()
    render_session.on_rendered.append(accumulate_assets)
    render_session.css_mode = AssetMode.INLINE
    render_session.js_mode = AssetMode.INLINE
    return render_session


@pytest.fixture
def scope(session, ctx):
    """An active request scope carrying the load context, yielding the session."""
    with request_scope(session=session, load_context=ctx) as active:
        yield active
