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

`reactive_dev`, `inject_htmx`, and any other `PjxSettings` field are passed through `**kwargs`, not declared as their own keywords — an unrecognized keyword raises `TypeError`. `components_root` and `static_root` default to an unset sentinel rather than `None`, so a caller can pass every field through unconditionally without needing to say anything about the ones it was never given; explicitly passing `None` is a real value and does override.

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

1. `configure_pyjinhx(settings)` — publish settings for the process, apply reactive dev
2. Your existing lifespan startup (if any)
3. Serve traffic
4. Your existing lifespan shutdown
5. `shutdown_pyjinhx()`

Does **not** compose deprecated `@app.on_event("startup")` handlers — use the lifespan API.

## PjxSettings

```python
@dataclass(frozen=True)
class PjxSettings:
    reactive_dev: bool = False
    inject_htmx: bool = True
    components_root: Path | str | None = None
    static_root: Path | str | None = None
```

- `reactive_dev` — enables reactive dev guardrails when true.
- `inject_htmx` — stored only; how it maps onto the session's asset modes is pending design.
- `components_root` — directory walked for component discovery; `None` is a no-op.
- `static_root` — directory mounted as static assets when `setup(app, ...)` is given an app; `None` is a no-op.

### from_env

```python
@classmethod
def from_env(cls) -> PjxSettings
```

| Variable | Default | Effect |
|----------|---------|--------|
| `PJX_REACTIVE_DEV` | off | Sets `reactive_dev`; accepts `1`/`true`/`yes`/`on` (and `0`/`false`/`no`/`off`) |
| `PJX_INJECT_HTMX` | on | Sets `inject_htmx`; same boolean parsing as above |
| `PJX_COMPONENTS_ROOT` | unset | Sets `components_root` from a filesystem path |
| `PJX_STATIC_ROOT` | unset | Sets `static_root` from a filesystem path |

## configure_pyjinhx / shutdown_pyjinhx

Lower-level process hooks used by `setup()` and tests:

```python
configure_pyjinhx(settings)  # startup
shutdown_pyjinhx()  # shutdown
```

`configure_pyjinhx` publishes `settings` as the process's current configuration (readable via `current_settings()`) and applies `reactive_dev` by toggling `pyjinhx.dev`, if that module is importable. `shutdown_pyjinhx` resets the process back to default `PjxSettings()` and disables reactive dev the same way.

