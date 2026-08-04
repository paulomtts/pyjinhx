# Usage tiers

PyJinHx is one library with optional layers. Adopt each tier only when you need it.

The Guide is organized in two halves that map onto these tiers:

- **Basic** (Tier 1) — declare components, compose them with PascalCase tags and nesting, and let asset collection bundle their CSS/JS. No framework wiring. This is all you need for templating and server-rendered HTML.
- **Advanced** (Tiers 2–4) — request scoping, reactive HTMX, configuration, loading states, and integrations (FastAPI, HTMX, …). Everything where the framework wires behavior for you.

**Source layout:** the engine is a mostly flat package — modules live directly under `pyjinhx/` (e.g. `_component`, `rendering`, `responses`, `session`, `config`), with the reactive layer as the one subpackage (`pyjinhx.reactive`). Public imports stay on `from pyjinhx import ...`.

## Tier 1 — Components

**What:** `BaseComponent` + co-located Jinja templates + a `RenderSession`.

**Use when:** Scripts, static pages, or any server-rendered HTML without per-request state sharing.

```python
from pyjinhx import BaseComponent
from pyjinhx.session import RenderSession


class Button(BaseComponent):
    id: str
    text: str


session = RenderSession()
html = Button(id="cta", text="Click").render(session)
```

**Docs:** [Quick Start](../getting-started/quickstart.md), [Creating Components](components.md)

---

## Tier 2 — Web app scoping

**What:** `request_scope()` per HTTP request.

**Use when:** FastAPI, Starlette, or any multi-request server — isolates component instances so request A cannot leak into request B. Also initializes the request-tier load cache layer and resets mutation tracking.

```python
from pyjinhx.session import request_scope

with request_scope():
    return MyPage(id="app").render()
```

`load_context` is **optional** — bare `request_scope()` is valid.

**Docs:** [Component Registry](registry.md), [FastAPI integration](../integrations/fastapi.md)

---

## Tier 3 — Reactive HTMX

**What:** `ReactiveComponent`, `@mutates`, dependency-aware OOB swaps.

**Use when:** HTMX apps where one mutation should update multiple regions without manual swap wiring.

```python
@app.post("/todos/toggle")
def toggle(todo_id: int):
    store.toggle(todo_id)
    return ItemRow(todo_id=todo_id, id=f"row-{todo_id}")
```

Return the component itself. `render()` returns that one component's markup and nothing else — the OOB legs for its dependents are attached afterwards, by the response composer, when the handler's return is turned into a response (see [Response composition](../api/responses.md)).

A `ReactiveComponent` can optionally declare the `react=(...)` class keyword (the state keys it derives from); it defaults to no dependencies and is used alongside `load()`.

Fan-out is unconditional: `compose()` walks the manifest on every response it builds a body for. A registered `IntegrationBackend` (wired automatically by `setup(app)` for supported frameworks) is what parses the client's mounted-region manifest off the request headers onto the session — with no backend the session simply carries an empty manifest, so there is nothing mounted to swap.

"Auto-dirtied" means a `@mutates`-decorated store method records the dirtied state keys it touched; the composer consumes them to decide which mounted regions to reload and swap.

**Docs:** [Reactivity](../reactivity.md), [HTMX integration](../integrations/htmx.md)

---

## Tier 4 — Full wiring

**What:** Optional pieces on top of Tier 3.

| Piece | Purpose |
|-------|---------|
| `load_context=` in `request_scope` | Pass DB/store into `load()` without globals |
| `IntegrationBackend` (registered via `register_backend()` / `setup(app)`) | Middleware parses `X-PJX-Mounted` / `X-PJX-Assets` onto the session, for `compose()` to consume |
| Load cache + `invalidate()` | Cache `load()` results; evict on mutation |
| `enable_reactive_dev()` | Warnings for dirtied keys nothing in the request loaded under |
| `pyjinhx.builtins` | Optional pre-built UI kit |

**Canonical wiring** — `setup(app, ...)` installs `PjxScopeMiddleware`, which opens the request scope and parses the pjx headers onto the session:

```python
from pyjinhx import setup

setup(app, context_factory=lambda request: AppLoadContext(db=get_db(request)))
```

See [FastAPI integration § Middleware](../integrations/fastapi.md#middleware-recommended).

**Docs:** [Build an App](../getting-started/build-an-app.md), [Client Backend](../api/client-backend.md), [Cache & Invalidation](../api/cache-invalidation.md)
