# Reactive todo demo

A minimal FastAPI + htmx app showing pyjinhx dependency-aware reactivity end to end.

```bash
uv run uvicorn examples.reactive_todo.app:app --reload
# open http://127.0.0.1:8000
```

What to watch (open the network tab):

- **Toggle** a todo → the row swaps (primary), and the **"N left"** counter and
  **"Clear completed (M)"** button update out-of-band. The **"N total"** badge does
  *not* re-send — a toggle doesn't change the total, so hash-gating skips it.
- **Add** a todo → the row is appended; counter and total update; the clear button is
  skipped (completed count unchanged).
- **Clear completed** → the list and total update; the **"N left"** counter is skipped
  (remaining is unchanged).

The routes never mention the counter/total/clear button — they just declare
`dirtied={"todos"}`. The dependency graph lives on the components (`reacts_to`), and
`pjx.js` reports what's mounted via the `X-PJX-Mounted` header.

## Load cache + invalidation

On startup the app calls `configure_load_cache()` (FastAPI lifespan). Default is
**`CacheScope.PROCESS`** — cross-request `load()` caching per worker. Correctness
depends on proper invalidation (`@mutates`, `dirty_keys`, reactive `render()`).

Per-request cache only (multi-worker safe without Redis):

```bash
PJX_LOAD_CACHE_SCOPE=request uv run uvicorn examples.reactive_todo.app:app --reload
```

Multi-worker with Redis fan-out:

```bash
PJX_LOAD_CACHE_SCOPE=process REDIS_URL=redis://localhost:6379/0 \
  uv run uvicorn examples.reactive_todo.app:app --reload
```

Copy `redis_invalidation.py` into your own project to adapt the backend. Dev deps: `fakeredis`, `redis`.
