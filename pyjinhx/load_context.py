from __future__ import annotations

import inspect
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

_load_context: ContextVar[Any | None] = ContextVar("load_context", default=None)


@dataclass(frozen=True)
class LoadContext:
    """
    Opaque base for request-scoped data available inside reactive ``load()``.

    Subclass or replace with your own frozen dataclass; set per request via
    ``load_scope()`` or ``Registry.request_scope(load_context=...)``.
    """


def get_load_context() -> Any | None:
    """Return the current load context, or ``None`` outside a scope."""
    return _load_context.get()


@contextmanager
def load_scope(ctx: Any) -> Generator[None, None, None]:
    """Set the load context for the current scope."""
    token = _load_context.set(ctx)
    try:
        yield
    finally:
        _load_context.reset(token)


def load_accepts_ctx(func: Any) -> bool:
    """Return whether ``func`` accepts a keyword-only ``ctx`` argument."""
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    param = signature.parameters.get("ctx")
    return param is not None and param.kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
