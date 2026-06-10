# Configuration

Process-wide setup and optional FastAPI/Starlette wiring via a single entry point.

## setup

```python
def setup(
    app: object | None = None,
    *,
    settings: PjxSettings | None = None,
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

1. `configure_pyjinhx(settings)` — derive cache scope from the backend, optional invalidation listener, reactive dev
2. Your existing lifespan startup (if any)
3. Serve traffic
4. Your existing lifespan shutdown
5. `shutdown_pyjinhx()`

Does **not** compose deprecated `@app.on_event("startup")` handlers — use the lifespan API.

## PjxSettings

```python
@dataclass(frozen=True)
class PjxSettings:
    invalidation_backend: InvalidationBackend | None = None
    reactive_dev: bool = False
```

The load-cache scope is not a field — it is derived from `invalidation_backend`. A backend (kept consistent across workers) enables cross-request caching per worker process; without one, `load()` results are cached per request only.

### from_env

```python
@classmethod
def from_env(cls) -> PjxSettings
```

| Variable | Default | Effect |
|----------|---------|--------|
| `REDIS_URL` | unset | Auto-wire `RedisInvalidationBackend` (derives cross-request caching) |
| `PJX_INVALIDATION_DB` | unset | Auto-wire `SqliteInvalidationBackend` from a SQLite file path (single-host; ignored if `REDIS_URL` is also set) |
| `PJX_REACTIVE_DEV` | off | Enable dev guardrails when `1`/`true`/`yes` |

## configure_pyjinhx / shutdown_pyjinhx

Lower-level process hooks used by `setup()` and tests:

```python
configure_pyjinhx(settings)   # startup
shutdown_pyjinhx()            # shutdown
```

When an `invalidation_backend` is configured, its listener starts and cross-request (process-wide) caching is enabled; otherwise caching is per-request.

## pyjinhx_lifespan

Sync context manager for non-ASGI tests and scripts:

```python
with pyjinhx_lifespan():
    ...
```

## Cache defaults

By default (no backend), `load()` caching is **per request** — multi-worker safe without Redis. Pass an `invalidation_backend` to opt into cross-request caching per worker process:

```python
setup(app, invalidation_backend=...)
```

See [Cache & Invalidation](cache-invalidation.md) and [Redis integration](integrations-redis.md).
