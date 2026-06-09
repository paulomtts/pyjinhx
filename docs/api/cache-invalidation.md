# Cache & Invalidation

Public API for the reactive `load()` cache and cross-process invalidation fan-out.

See [Reactivity](../reactivity.md) and [FastAPI integration](../integrations/fastapi.md) for usage patterns.

## CacheScope

```python
class CacheScope(str, Enum):
    REQUEST = "request"
    PROCESS = "process"
    NONE = "none"
```

Controls where cached `load()` results are stored.

| Scope | Behavior |
|-------|----------|
| `REQUEST` (default) | Isolated per `Registry.request_scope()`; cleared when the scope exits |
| `PROCESS` | Shared per worker process; survives across HTTP requests |
| `NONE` | No caching; every `load()` runs fresh |

`Registry.request_scope()` always creates a request-scoped cache store. With `PROCESS` scope, reads fall through to the process store; with `REQUEST` scope, only the request store is used.

## LoadCache

```python
class LoadCache:
    @classmethod
    def scope(cls) -> CacheScope: ...
    @classmethod
    def set_scope(cls, scope: CacheScope) -> None: ...
    @classmethod
    def invalidate(cls, dirtied: Iterable[object], *, propagate: bool = True) -> None: ...
    @classmethod
    def clear(cls) -> None: ...
```

Memoizes reactive `load()` results keyed by `(class, load_arg)`.

Prefer [`setup()`](config.md) at app startup:

```python
from pyjinhx import CacheScope, setup

setup(app, cache_scope=CacheScope.REQUEST)   # default — multi-worker safe
setup(app, cache_scope=CacheScope.PROCESS)   # cross-request per worker; pair with invalidation
```

Or set explicitly: `LoadCache.set_scope(CacheScope.REQUEST)`.

Environment variable `PJX_LOAD_CACHE_SCOPE` is read by `PjxSettings.from_env()` (default `request`).

**Propagation:** when `CacheScope.PROCESS` is active, an `InvalidationBackend` is configured, and `propagate=True` (default), dirtied keys are published to other workers after local eviction. Remote handlers call `LoadCache.invalidate(..., propagate=False)` to avoid publish loops.

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
from pyjinhx import setup, PjxSettings, CacheScope
from pyjinhx.integrations.redis import RedisInvalidationBackend

setup(
    app,
    settings=PjxSettings(
        cache_scope=CacheScope.PROCESS,
        invalidation_backend=RedisInvalidationBackend("redis://localhost:6379/0"),
    ),
)
```

See [Configuration](config.md).
