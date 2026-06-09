# Configuration

Process-wide setup and optional FastAPI/Starlette wiring via a single entry point.

## setup

```python
def setup(
    app: object | None = None,
    *,
    settings: PjxSettings | None = None,
    cache_scope: CacheScope = CacheScope.REQUEST,
    invalidation_backend: InvalidationBackend | None = None,
    reactive_dev: bool = False,
    load_context_factory: Callable[[Any], object | None] | None = None,
    **kwargs: Any,
) -> PjxSettings
```

**Single call** for typical web apps:

```python
from fastapi import FastAPI
from pyjinhx import setup

app = FastAPI()
setup(app, load_context_factory=lambda req: AppLoadContext(db=get_db(req)))
```

| `app` | Behavior |
|-------|----------|
| FastAPI/Starlette app | Chain lifespan (preserve existing) + register registry middleware |
| `None` | Process config only (`configure_pyjinhx`) — tests, scripts |

Idempotent: a second `setup(app, ...)` on the same app is a no-op.

### Lifespan chaining

When `app` is provided, pyjinhx wraps `app.router.lifespan_context`:

1. `configure_pyjinhx(settings)` — cache scope, optional invalidation listener, reactive dev
2. Your existing lifespan startup (if any)
3. Serve traffic
4. Your existing lifespan shutdown
5. `shutdown_pyjinhx()`

Does **not** compose deprecated `@app.on_event("startup")` handlers — use the lifespan API.

## PjxSettings

```python
@dataclass(frozen=True)
class PjxSettings:
    cache_scope: CacheScope = CacheScope.REQUEST
    invalidation_backend: InvalidationBackend | None = None
    reactive_dev: bool = False
```

### from_env

```python
@classmethod
def from_env(cls) -> PjxSettings
```

| Variable | Default | Effect |
|----------|---------|--------|
| `PJX_LOAD_CACHE_SCOPE` | `request` | `CacheScope` for `load()` cache |
| `PJX_REACTIVE_DEV` | off | Enable dev guardrails when `1`/`true`/`yes` |
| `REDIS_URL` | unset | When scope is `process`, auto-wire `RedisInvalidationBackend` |

## configure_pyjinhx / shutdown_pyjinhx

Lower-level process hooks used by `setup()` and tests:

```python
configure_pyjinhx(settings)   # startup
shutdown_pyjinhx()            # shutdown
```

Invalidation backend starts only when `cache_scope == PROCESS` and a backend is configured.

## pyjinhx_lifespan

Sync context manager for non-ASGI tests and scripts:

```python
with pyjinhx_lifespan(cache_scope=CacheScope.REQUEST):
    ...
```

## Environment defaults

Default **`CacheScope.REQUEST`** — multi-worker safe without Redis. Opt into cross-request caching:

```python
setup(app, cache_scope=CacheScope.PROCESS, invalidation_backend=...)
```

See [Cache & Invalidation](cache-invalidation.md) and [Redis integration](integrations-redis.md).
