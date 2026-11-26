"""Shared fixtures for the todo example's component tests.

Every test runs inside its own request_scope: load() results are memoized per
request, so a shared scope would let one test's cached load leak into the next.
"""

from pathlib import Path

import pytest

from examples import todo
from examples.todo import store as todo_store
from examples.todo.context import TodoAppContext
from pyjinhx import setup
from pyjinhx.rendering.assets import AssetMode
from pyjinhx.rendering.session import RenderSession, accumulate_assets, request_scope


@pytest.fixture(autouse=True)
def todo_registry():
    """Publish the todo app's components for every test."""
    # The app publishes them once, at import. Tests elsewhere empty the
    # registry, which would leave these rendering their child tags unresolved.
    setup(components_root=Path(todo.__file__).parent / "components")


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
    inline_session = RenderSession()
    inline_session.on_rendered.append(accumulate_assets)
    inline_session.css_mode = AssetMode.INLINE
    inline_session.js_mode = AssetMode.INLINE
    return inline_session


@pytest.fixture
def scope(session, ctx):
    """An active request scope carrying the load context, yielding the session."""
    with request_scope(session=session, load_context=ctx) as active:
        yield active
