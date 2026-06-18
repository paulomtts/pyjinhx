from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from typing import Any

from pyjinhx.cache import CacheScope, InvalidationBackend, InvalidationHub, LoadCache
from pyjinhx.dev import disable_reactive_dev, enable_reactive_dev

_UNSET: Any = (
    object()
)  # sentinel: distinguishes "argument omitted" from None / a real value


@dataclass(frozen=True)
class PjxSettings:
    invalidation_backend: InvalidationBackend | None = None
    reactive_dev: bool = False
    inject_htmx: bool = True

    @classmethod
    def from_env(cls) -> PjxSettings:
        reactive_dev = os.environ.get("PJX_REACTIVE_DEV", "").lower() in {
            "1",
            "true",
            "yes",
        }
        inject_htmx = os.environ.get("PJX_INJECT_HTMX", "").lower() not in {
            "0",
            "false",
            "no",
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
            inject_htmx=inject_htmx,
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
    inject_htmx: Any,
    extra: dict[str, Any],
) -> PjxSettings:
    return (settings or PjxSettings()).merge(
        invalidation_backend=invalidation_backend,
        reactive_dev=reactive_dev,
        inject_htmx=inject_htmx,
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
            inject_htmx=kwargs.pop("inject_htmx", _UNSET),
            extra=kwargs,
        )
    else:
        resolved = settings

    # The cache scope follows the backend: a cross-worker invalidation backend
    # (e.g. Redis) makes cross-request PROCESS caching safe across workers; without
    # one, the only multi-worker-safe behavior is per-request (REQUEST) caching.
    backend = resolved.invalidation_backend
    LoadCache.set_scope(
        CacheScope.PROCESS if backend is not None else CacheScope.REQUEST
    )

    InvalidationHub.set_backend(backend)
    if backend is not None:
        InvalidationHub.start_listener()

    if resolved.reactive_dev:
        enable_reactive_dev()
    else:
        disable_reactive_dev()

    from pyjinhx.assets import set_inject_htmx

    set_inject_htmx(resolved.inject_htmx)

    return resolved


def shutdown_pyjinhx() -> None:
    InvalidationHub.stop_listener()
    InvalidationHub.set_backend(None)
    disable_reactive_dev()


def _is_asgi_app(app: object) -> bool:
    return hasattr(app, "add_middleware") and hasattr(app, "router")


def setup(
    app: object | None = None,
    *,
    settings: PjxSettings | None = None,
    context_factory: Callable[[Any], object | None] | None = None,
    invalidation_backend: InvalidationBackend | None = _UNSET,
    reactive_dev: bool = _UNSET,
    inject_htmx: bool = _UNSET,
    components_root: str | os.PathLike[str] | None = None,
    static_root: str | os.PathLike[str] | None = None,
    **kwargs: Any,
) -> PjxSettings:
    """
    Wire pyjinhx for this process (and optionally a web app).

    With ``app=None``, only process-wide configuration runs (tests, scripts).
    With a FastAPI/Starlette app, lifespan is chained and registry middleware
    is registered.

    ``components_root`` sets the renderer's default environment to a
    ``FileSystemLoader`` rooted there (works with or without an ``app``).
    ``static_root`` mounts a ``StaticFiles`` app at ``/static`` and therefore
    requires an ``app``.

    The load-cache scope is derived from ``invalidation_backend``: cross-request
    ``PROCESS`` caching when a backend is set (kept consistent across workers by
    the backend), per-request ``REQUEST`` caching otherwise.

    ``inject_htmx`` (default ``True``) inlines a vendored htmx ahead of the
    pyjinhx runtime on reactive root renders, so reactivity works out of the
    box. Set it to ``False`` if you load/manage htmx yourself; the inlined copy
    self-guards against double-load regardless.
    """
    if components_root is not None:
        from pyjinhx.renderer import Renderer

        Renderer.set_default_environment(components_root)
    if static_root is not None and app is None:
        raise TypeError("setup(static_root=...) requires an app to mount it on")
    resolved = _merge_settings(
        settings,
        invalidation_backend=invalidation_backend,
        reactive_dev=reactive_dev,
        inject_htmx=inject_htmx,
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

    apply_setup(app, resolved, context_factory=context_factory, static_root=static_root)
    return resolved
