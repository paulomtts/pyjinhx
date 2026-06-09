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

**Loading shimmer:** `Counter` and `Total` set `loading_skeleton = True`, so when you
toggle/add a todo they show a shimmer over their current value until the server's fresh
value swaps in. (Each `load()` has a small artificial `time.sleep` so the effect is
visible on a fast local server — remove it in real apps.)

The routes never mention the counter/total/clear button — `@mutates` and
`@mutates` accumulates dirtied keys automatically, and `setup()` wires
`ClientBackend` so `render()` reads `X-PJX-Mounted` from the request.
The dependency graph lives on the components (`reacts_to`), and `pjx.js` reports
what's mounted on every HTMX request.

## Setup

The app calls `setup(app, ...)` once — lifespan (cache + optional invalidation) and
registry middleware are wired automatically. Default load cache is
**`CacheScope.REQUEST`** (multi-worker safe without Redis).

Cross-request cache per worker (opt-in performance):

```bash
PJX_LOAD_CACHE_SCOPE=process uv run uvicorn examples.reactive_todo.app:app --reload
```

Multi-worker with Redis invalidation fan-out:

```bash
PJX_LOAD_CACHE_SCOPE=process REDIS_URL=redis://localhost:6379/0 \
  uv run uvicorn examples.reactive_todo.app:app --reload
```

Redis backend: `pyjinhx.integrations.redis.RedisInvalidationBackend` (`pip install pyjinhx[redis]`).
