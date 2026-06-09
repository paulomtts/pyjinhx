from __future__ import annotations

import logging
import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, fields, replace
from typing import Any

from pyjinhx.cache import CacheScope, LoadCache, InvalidationBackend, InvalidationHub
from pyjinhx.dev import disable_reactive_dev, enable_reactive_dev


logger = logging.getLogger("pyjinhx")


_UNSET: Any = object()  # sentinel: distinguishes "argument omitted" from None / a real value


@dataclass(frozen=True)
class PjxSettings:
    cache_scope: CacheScope = CacheScope.REQUEST
    invalidation_backend: InvalidationBackend | None = None
    reactive_dev: bool = False

    @classmethod
    def from_env(cls) -> PjxSettings:
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
            from pyjinhx.integrations.redis import RedisInvalidationBackend

            invalidation_backend = RedisInvalidationBackend(redis_url)
        return cls(
            cache_scope=cache_scope,
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
    cache_scope: Any,
    invalidation_backend: Any,
    reactive_dev: Any,
    extra: dict[str, Any],
) -> PjxSettings:
    return (settings or PjxSettings()).merge(
        cache_scope=cache_scope,
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
            cache_scope=kwargs.pop("cache_scope", _UNSET),
            invalidation_backend=kwargs.pop("invalidation_backend", _UNSET),
            reactive_dev=kwargs.pop("reactive_dev", _UNSET),
            extra=kwargs,
        )
    else:
        resolved = settings

    LoadCache.set_scope(resolved.cache_scope)

    if (
        resolved.invalidation_backend is not None
        and resolved.cache_scope != CacheScope.PROCESS
    ):
        logger.warning(
            "invalidation_backend is configured but cache_scope is %s; "
            "cross-process invalidation requires CacheScope.PROCESS — ignoring backend",
            resolved.cache_scope.value,
        )
        resolved = replace(resolved, invalidation_backend=None)

    if resolved.invalidation_backend is not None and resolved.cache_scope == CacheScope.PROCESS:
        InvalidationHub.set_backend(resolved.invalidation_backend)
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
    cache_scope: CacheScope = _UNSET,
    invalidation_backend: InvalidationBackend | None = _UNSET,
    reactive_dev: bool = _UNSET,
    load_context_factory: Callable[[Any], object | None] | None = None,
    **kwargs: Any,
) -> PjxSettings:
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
    from pyjinhx.integrations.fastapi import apply_setup

    apply_setup(app, resolved, load_context_factory=load_context_factory)
    return resolved
