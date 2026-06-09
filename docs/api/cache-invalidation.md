# Cache & Invalidation

Public API for the reactive `load()` cache and cross-process invalidation fan-out.

See [Reactivity](../reactivity.md) and [FastAPI integration](../integrations/fastapi.md) for usage patterns.

## Cache scope

You don't choose where cached `load()` results are stored — it is **derived** from whether an `invalidation_backend` is configured:

| Backend | Behavior |
|---------|----------|
| none (default) | Per-request: isolated per `Registry.request_scope()`, cleared when the scope exits — the only multi-worker-safe default |
| configured (e.g. Redis) | Per worker process: results survive across HTTP requests, with the backend keeping every worker's cache consistent on mutation |

`Registry.request_scope()` always creates a request-scoped cache store, so the within-request dedup that the reactive OOB walk relies on always happens. With a backend configured, reads also fall through to the process store; otherwise only the request store is used.

## LoadCache

```python
class LoadCache:
    @classmethod
    def invalidate(cls, dirtied: Iterable[object], *, propagate: bool = True) -> None: ...
    @classmethod
    def clear(cls) -> None: ...
```

Memoizes reactive `load()` results keyed by `(class, load_arg)`. The scope is set for you from the configured backend (see above) — use [`setup()`](config.md) at app startup:

```python
from pyjinhx import setup

setup(app)                      # default — per-request, multi-worker safe
setup(app, invalidation_backend=...)  # cross-request per worker; fans out evictions
```

**Propagation:** when an `InvalidationBackend` is configured (cross-request caching active) and `propagate=True` (default), dirtied keys are published to other workers after local eviction. Remote handlers call `LoadCache.invalidate(..., propagate=False)` to avoid publish loops.

Called automatically by `@mutates` after mutations complete.

## InvalidationBackend

```python
class InvalidationBackend(ABC):
    def publish(self, keys: frozenset[str]) -> None: ...
    def start(self, handler: Callable[[frozenset[str]], None]) -> None: ...
    def stop(self) -> None: ...
```

Abstract base class for cross-process invalidation. Implement `publish()` to broadcast dirtied keys and `start()`/`stop()` to manage a subscriber that invokes the handler on incoming messages.

A reference Redis implementation lives in [`pyjinhx.integrations.redis`](integrations-redis.md).

## InvalidationHub

```python
class InvalidationHub:
    @classmethod
    def set_backend(cls, backend: InvalidationBackend | None) -> None: ...
    @classmethod
    def start_listener(cls) -> None: ...
    @classmethod
    def stop_listener(cls) -> None: ...
```

Runtime coordinator for cross-process invalidation. Passing a new backend stops the previous one if a listener was running.

`start_listener()` raises `RuntimeError` if no backend is configured. Idempotent — safe to call multiple times.

**Typical FastAPI setup:**

```python
from pyjinhx import setup, PjxSettings
from pyjinhx.integrations.redis import RedisInvalidationBackend

setup(
    app,
    settings=PjxSettings(
        invalidation_backend=RedisInvalidationBackend("redis://localhost:6379/0"),
    ),
)
```

See [Configuration](config.md).
