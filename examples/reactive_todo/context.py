from dataclasses import dataclass

from pyjinhx import PjxContext


@dataclass(frozen=True)
class AppLoadContext:
    """Request-scoped access to the demo store module."""

    store: object


def _store():
    ctx = PjxContext.current()
    if isinstance(ctx, AppLoadContext):
        return ctx.store
    from . import store

    return store
