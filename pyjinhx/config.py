from __future__ import annotations

import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, fields, replace
from typing import Any

from pyjinhx.cache import CacheScope, InvalidationBackend, InvalidationHub, LoadCache
from pyjinhx.dev import disable_reactive_dev, enable_reactive_dev

_UNSET: Any = object()  # sentinel: distinguishes "argument omitted" from None / a real value


@dataclass(frozen=True)
class PjxSettings:
    invalidation_backend: InvalidationBackend | None = None
    reactive_dev: bool = False

    @classmethod
    def from_env(cls) -> PjxSettings:
        reactive_dev = os.environ.get("PJX_REACTIVE_DEV", "").lower() in {
            "1",
            "true",
            "yes",
        }
        invalidation_backend: InvalidationBackend | None = None
        redis_url = os.environ.get("REDIS_URL")
        sqlite_db = os.environ.get("PJX_INVALIDATION_DB")
        if redis_url:
            from pyjinhx.integrations.redis import RedisInvalidationBackend

            invalidation_backend = RedisInvalidationBackend(redis_url)
        elif sqlite_db:
            from pyjinhx.integrations.sqlite import SqliteInvalidationBackend

            invalidation_backend = SqliteInvalidationBackend(sqlite_db)
        return cls(
            invalidation_backend=invalidation_backend,
            reactive_dev=reactive_dev,
        )

    def merge(self, **overrides: Any) -> PjxSettings:
        # only fields explicitly provided (not the _UNSET sentinel) override self, so an
        # explicit `settings=` is never clobbered by setup()'s default keyword arguments
        valid = {field.name for field in fields(self)}
        filtered = {
            key: value
            for key, value in overrides.items()
            if key in valid and value is not _UNSET
        }
        return replace(self, **filtered)


def _merge_settings(
    settings: PjxSettings | None,
    *,
    invalidation_backend: Any,
    reactive_dev: Any,
    extra: dict[str, Any],
) -> PjxSettings:
    return (settings or PjxSettings()).merge(
        invalidation_backend=invalidation_backend,
        reactive_dev=reactive_dev,
        **extra,
    )


def configure_pyjinhx(
    settings: PjxSettings | None = None,
    /,
    **kwargs: Any,
) -> PjxSettings:
    if kwargs or settings is None:
        resolved = _merge_settings(
            settings,
            invalidation_backend=kwargs.pop("invalidation_backend", _UNSET),
            reactive_dev=kwargs.pop("reactive_dev", _UNSET),
            extra=kwargs,
        )
    else:
        resolved = settings

    # The cache scope follows the backend: a cross-worker invalidation backend
    # (e.g. Redis) makes cross-request PROCESS caching safe across workers; without
    # one, the only multi-worker-safe behavior is per-request (REQUEST) caching.
    backend = resolved.invalidation_backend
    LoadCache.set_scope(CacheScope.PROCESS if backend is not None else CacheScope.REQUEST)

    if backend is not None:
        InvalidationHub.set_backend(backend)
        InvalidationHub.start_listener()
    else:
        InvalidationHub.set_backend(None)

    if resolved.reactive_dev:
        enable_reactive_dev()
    else:
        disable_reactive_dev()

    return resolved


def shutdown_pyjinhx() -> None:
    InvalidationHub.stop_listener()
    InvalidationHub.set_backend(None)
    disable_reactive_dev()


@contextmanager
def pyjinhx_lifespan(
    settings: PjxSettings | None = None,
    /,
    **kwargs: Any,
) -> Generator[None, None, None]:
    configure_pyjinhx(settings, **kwargs)
    try:
        yield
    finally:
        shutdown_pyjinhx()


def _is_asgi_app(app: object) -> bool:
    return hasattr(app, "add_middleware") and hasattr(app, "router")


def setup(
    app: object | None = None,
    *,
    settings: PjxSettings | None = None,
    invalidation_backend: InvalidationBackend | None = _UNSET,
    reactive_dev: bool = _UNSET,
    context_factory: Callable[[Any], object | None] | None = None,
    **kwargs: Any,
) -> PjxSettings:
    """
    Wire pyjinhx for this process (and optionally a web app).

    With ``app=None``, only process-wide configuration runs (tests, scripts).
    With a FastAPI/Starlette app, lifespan is chained and registry middleware
    is registered.

    The load-cache scope is derived from ``invalidation_backend``: cross-request
    ``PROCESS`` caching when a backend is set (kept consistent across workers by
    the backend), per-request ``REQUEST`` caching otherwise.
    """
    resolved = _merge_settings(
        settings,
        invalidation_backend=invalidation_backend,
        reactive_dev=reactive_dev,
        extra=kwargs,
    )
    if app is None:
        configure_pyjinhx(resolved)
        return resolved
    if not _is_asgi_app(app):
        raise TypeError(
            "setup(app=...) requires a Starlette/FastAPI-like app "
            "with add_middleware and router"
        )
    from pyjinhx.integrations.fastapi import apply_setup

    apply_setup(app, resolved, context_factory=context_factory)
    return resolved
