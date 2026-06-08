# Usage tiers

PyJinHx is one library with optional layers. Adopt each tier only when you need it.

## Tier 1 — Components

**What:** `BaseComponent` + co-located Jinja templates + `Renderer`.

**Use when:** Scripts, static pages, or any server-rendered HTML without per-request state sharing.

```python
from pyjinhx import BaseComponent, Renderer

Renderer.set_default_environment("./components")

class Button(BaseComponent):
    id: str
    text: str

html = Button(id="cta", text="Click").render()
```

**Docs:** [Quick Start](../getting-started/quickstart.md), [Creating Components](components.md)

---

## Tier 2 — Web app scoping

**What:** `Registry.request_scope()` per HTTP request.

**Use when:** FastAPI, Starlette, or any multi-request server — isolates component instances so request A cannot leak into request B. Also initializes the request-tier load cache layer and resets mutation tracking.

```python
from pyjinhx import Registry

with Registry.request_scope():
    return MyPage(id="app").render()
```

`load_context` and `client_backend` are **optional** — bare `request_scope()` is valid.

**Docs:** [Component Registry](registry.md), [FastAPI integration](../integrations/fastapi.md)

---

## Tier 3 — Reactive HTMX

**What:** `ReactiveComponent`, `@mutates`, dependency-aware OOB swaps.

**Use when:** HTMX apps where one mutation should update multiple regions without manual swap wiring.

```python
@app.post("/todos/toggle")
def toggle(todo_id: int):
    store.toggle(todo_id)
    return TodoItemRow.render(todo_id)  # OOB for dependents
```

Requires `Registry.request_scope()` on every request when using auto-dirtied from `@mutates`.

**Docs:** [Reactivity](../reactivity.md), [HTMX integration](../integrations/htmx.md)

---

## Tier 4 — Full wiring

**What:** Optional pieces on top of Tier 3.

| Piece | Purpose |
|-------|---------|
| `load_context=` in `request_scope` | Pass DB/store into `load()` without globals |
| `client_backend=` in `request_scope` | Auto `X-PJX-Mounted` / `X-PJX-Assets` in `render()` |
| Load cache + `invalidate()` | Cache `load()` results; evict on mutation |
| `InvalidationBackend` | Cross-worker cache fan-out |
| `enable_reactive_dev()` | Warnings for missing `mounted`, unconsumed `@mutates`, etc. |
| `pyjinhx.builtins` | Optional pre-built UI kit |

**Canonical middleware** (app-defined — pyjinhx does not ship middleware):

```python
with Registry.request_scope(
    load_context=AppLoadContext(db=get_db(request)),
    client_backend=fastapi_client_backend(request),
):
    return await call_next(request)
```

See [FastAPI integration § Middleware](../integrations/fastapi.md#middleware-recommended).

**Docs:** [Build an App](../getting-started/build-an-app.md), [Client Backend](../api/client-backend.md), [Cache & Invalidation](../api/cache-invalidation.md)
