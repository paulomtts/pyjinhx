# Configuration

Process-wide setup and optional FastAPI/Starlette wiring via a single entry point.

## setup

```python
def setup(
    app: object | None = None,
    *,
    settings: PjxSettings | None = None,
    context_factory: Callable[[Any], object | None] | None = None,
    components_root: Path | str | None = ...,  # unset sentinel
    static_root: Path | str | None = ...,  # unset sentinel
    **kwargs: Any,
) -> PjxSettings
```

`invalidation_backend`, `reactive_dev`, and any other `PjxSettings` field are passed through `**kwargs`, not declared as their own keywords — an unrecognized keyword raises `TypeError`. `components_root` and `static_root` default to an unset sentinel rather than `None`, so a caller can pass every field through unconditionally without needing to say anything about the ones it was never given; explicitly passing `None` is a real value and does override.

`components_root` triggers component discovery (`build_registry()`) over that directory; it works with or without an `app`. `static_root` mounts a `StaticFiles` app at `/static` (name `"static"`) and therefore requires an `app` — passing it with `app=None` raises `TypeError`. When omitted, both are no-ops, and the static mount is covered by the idempotency guard, so a second `setup()` won't double-mount.

```python
app = FastAPI()
setup(app, components_root=COMPONENTS_ROOT, static_root=STATIC_ROOT)
```

**Single call** for typical web apps:

```python
from fastapi import FastAPI
from pyjinhx import setup

app = FastAPI()
setup(app, context_factory=lambda req: AppLoadContext(db=get_db(req)))
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
configure_pyjinhx(settings)  # startup
shutdown_pyjinhx()  # shutdown
```

When an `invalidation_backend` is configured, its listener starts and cross-request (process-wide) caching is enabled; otherwise caching is per-request.

