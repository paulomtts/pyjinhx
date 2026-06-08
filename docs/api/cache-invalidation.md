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

## get_load_cache_scope

```python
def get_load_cache_scope() -> CacheScope
```

Return the active process-wide cache scope.

## set_load_cache_scope

```python
def set_load_cache_scope(scope: CacheScope) -> None
```

Set the process-wide cache scope. Prefer [`setup()`](config.md) at app startup:

```python
from pyjinhx import CacheScope, setup

setup(app, cache_scope=CacheScope.REQUEST)   # default — multi-worker safe
setup(app, cache_scope=CacheScope.PROCESS)   # cross-request per worker; pair with invalidation
```

Or set explicitly: `set_load_cache_scope(CacheScope.REQUEST)`.

Environment variable `PJX_LOAD_CACHE_SCOPE` is read by `PyJinhxSettings.from_env()` (default `request`).

## invalidate

```python
def invalidate(dirtied: Iterable[object], *, propagate: bool = True) -> None
```

Evict every cached `load()` result whose interpolated reactive keys intersect the dirtied keys.

**Stem expansion:** invalidating `"todo"` evicts all instance-tier entries whose keys start with `"todo:"` (e.g. `"todo:42"`).

**Propagation:** when `CacheScope.PROCESS` is active, an `InvalidationBackend` is configured, and `propagate=True` (default), dirtied keys are published to other workers after local eviction. Remote handlers call `invalidate(..., propagate=False)` to avoid publish loops.

Called automatically by `@mutates` and `mutation_scope` after mutations complete.

## InvalidationBackend

```python
class InvalidationBackend(ABC):
    def publish(self, keys: frozenset[str]) -> None: ...
    def start(self, handler: Callable[[frozenset[str]], None]) -> None: ...
    def stop(self) -> None: ...
```

Abstract base class for cross-process invalidation. Implement `publish()` to broadcast dirtied keys and `start()`/`stop()` to manage a subscriber that invokes the handler on incoming messages.

A reference Redis implementation lives in [`pyjinhx.integrations.redis`](integrations-redis.md).

## set_invalidation_backend

```python
def set_invalidation_backend(backend: InvalidationBackend | None) -> None
```

Configure the invalidation backend. Passing a new backend stops the previous one if a listener was running.

## Listener lifecycle

### start_invalidation_listener

```python
def start_invalidation_listener() -> None
```

Start listening for remote invalidations. Raises `RuntimeError` if no backend is configured. Idempotent — safe to call multiple times.

### stop_invalidation_listener

```python
def stop_invalidation_listener() -> None
```

Stop the invalidation listener. Call during application shutdown.

**Typical FastAPI setup:**

```python
from pyjinhx import setup, PyJinhxSettings, CacheScope
from pyjinhx.integrations.redis import RedisInvalidationBackend

setup(
    app,
    settings=PyJinhxSettings(
        cache_scope=CacheScope.PROCESS,
        invalidation_backend=RedisInvalidationBackend("redis://localhost:6379/0"),
    ),
)
```

See [Configuration](config.md).
