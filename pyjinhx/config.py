from __future__ import annotations

import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, fields, replace
from typing import Any

from .cache import CacheScope, set_load_cache_scope
from .invalidation import (
    InvalidationBackend,
    set_invalidation_backend,
    start_invalidation_listener,
    stop_invalidation_listener,
)
from .reactive_dev import disable_reactive_dev, enable_reactive_dev


@dataclass(frozen=True)
class PyJinhxSettings:
    cache_scope: CacheScope = CacheScope.REQUEST
    invalidation_backend: InvalidationBackend | None = None
    reactive_dev: bool = False

    @classmethod
    def from_env(cls) -> PyJinhxSettings:
        scope_name = os.environ.get("PJX_LOAD_CACHE_SCOPE", "request").lower()
        cache_scope = CacheScope(scope_name)
        reactive_dev = os.environ.get("PJX_REACTIVE_DEV", "").lower() in {
            "1",
            "true",
            "yes",
        }
        invalidation_backend: InvalidationBackend | None = None
        redis_url = os.environ.get("REDIS_URL")
        if cache_scope == CacheScope.PROCESS and redis_url:
            from .integrations.redis import RedisInvalidationBackend

            invalidation_backend = RedisInvalidationBackend(redis_url)
        return cls(
            cache_scope=cache_scope,
            invalidation_backend=invalidation_backend,
            reactive_dev=reactive_dev,
        )


def _merge_settings(
    settings: PyJinhxSettings | None,
    *,
    cache_scope: CacheScope,
    invalidation_backend: InvalidationBackend | None,
    reactive_dev: bool,
    extra: dict[str, Any],
) -> PyJinhxSettings:
    valid = {field.name for field in fields(PyJinhxSettings)}
    overrides = {
        k: v
        for k, v in {
            "cache_scope": cache_scope,
            "invalidation_backend": invalidation_backend,
            "reactive_dev": reactive_dev,
            **extra,
        }.items()
        if k in valid
    }
    base = settings or PyJinhxSettings()
    return replace(base, **overrides)


def configure_pyjinhx(
    settings: PyJinhxSettings | None = None,
    /,
    **kwargs: Any,
) -> PyJinhxSettings:
    if kwargs or settings is None:
        resolved = _merge_settings(
            settings,
            cache_scope=kwargs.pop("cache_scope", CacheScope.REQUEST),
            invalidation_backend=kwargs.pop("invalidation_backend", None),
            reactive_dev=kwargs.pop("reactive_dev", False),
            extra=kwargs,
        )
    else:
        resolved = settings

    set_load_cache_scope(resolved.cache_scope)

    if resolved.invalidation_backend is not None and resolved.cache_scope == CacheScope.PROCESS:
        set_invalidation_backend(resolved.invalidation_backend)
        start_invalidation_listener()
    else:
        set_invalidation_backend(None)

    if resolved.reactive_dev:
        enable_reactive_dev()
    else:
        disable_reactive_dev()

    return resolved


def shutdown_pyjinhx() -> None:
    stop_invalidation_listener()
    set_invalidation_backend(None)
    disable_reactive_dev()


@contextmanager
def pyjinhx_lifespan(
    settings: PyJinhxSettings | None = None,
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
    settings: PyJinhxSettings | None = None,
    cache_scope: CacheScope = CacheScope.REQUEST,
    invalidation_backend: InvalidationBackend | None = None,
    reactive_dev: bool = False,
    load_context_factory: Callable[[Any], object | None] | None = None,
    **kwargs: Any,
) -> PyJinhxSettings:
    """
    Wire pyjinhx for this process (and optionally a web app).

    With ``app=None``, only process-wide configuration runs (tests, scripts).
    With a FastAPI/Starlette app, lifespan is chained and registry middleware
    is registered.
    """
    resolved = _merge_settings(
        settings,
        cache_scope=cache_scope,
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
    from .integrations.fastapi import apply_setup

    apply_setup(app, resolved, load_context_factory=load_context_factory)
    return resolved
