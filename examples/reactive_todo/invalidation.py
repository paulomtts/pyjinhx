"""
Load-cache configuration for the reactive todo demo.

Defaults to ``CacheScope.PROCESS`` (cross-request ``load()`` cache). Pair with
``REDIS_URL`` when running multiple workers so ``invalidate()`` fans out.

    PJX_LOAD_CACHE_SCOPE=request   # per-request cache only (multi-worker safe)
    REDIS_URL=redis://localhost:6379/0
    REDIS_URL=memory://            # fakeredis experiment, same process only
"""

from __future__ import annotations

import os

from pyjinhx import (
    CacheScope,
    set_invalidation_backend,
    set_load_cache_scope,
    start_invalidation_listener,
    stop_invalidation_listener,
)

from .redis_invalidation import RedisInvalidationBackend


def configure_load_cache() -> None:
    scope_name = os.environ.get("PJX_LOAD_CACHE_SCOPE", "process").lower()
    scope = CacheScope(scope_name)
    set_load_cache_scope(scope)

    redis_url = os.environ.get("REDIS_URL")
    if scope == CacheScope.PROCESS and redis_url:
        set_invalidation_backend(RedisInvalidationBackend(redis_url))
        start_invalidation_listener()


def shutdown_load_cache() -> None:
    stop_invalidation_listener()
