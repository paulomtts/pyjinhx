# Reactive todo demo

A minimal FastAPI + htmx app showing pyjinhx dependency-aware reactivity end to end.

Each component is a **single-file component** — its class and template live together in
one `.pjx` (`counter.pjx`, `item_row.pjx`, …, with the page shell in `page.pjx`),
imported directly with no build step. See `docs/single-file-components.md`.

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

**Loading indicators:** opt in *in the template* with `data-pjx-loading`. `item_row.html`
puts `data-pjx-loading="skeleton"` on the row (a silhouette shimmer while it reloads);
`clear_button.html` puts `data-pjx-loading="spinner"` on the button (a dim, blurred overlay +
circular progress). The element auto-triggers off its component's `react` keys, so toggling a
row or clearing shows the indicator until the fresh HTML swaps in. The toggle/clear routes
`time.sleep` briefly so this is visible on a fast local server — adding a todo stays instant
(no indicator). Set `PJX_DEMO_LATENCY=0` to disable; restyle via the `--pjx-*` CSS tokens
(see [Loading indicators](../../docs/reactivity.md)).

The routes never mention the counter/total/clear button — `@mutates` and
`@mutates` accumulates dirtied keys automatically, and `setup()` wires
`ClientBackend` so `render()` reads `X-PJX-Mounted` from the request.
The dependency graph lives on the components (`react` class keyword), and `pjx.js` reports
what's mounted on every HTMX request.

## Setup

The app calls `setup(app, ...)` once — lifespan (cache + optional invalidation) and
registry middleware are wired automatically. You don't choose a cache scope; it's derived
from the backend. With no backend (the default) `load()` results are cached per request,
which is multi-worker safe without Redis.

Cross-request cache per worker with Redis invalidation fan-out (opt-in performance, and the
multi-worker-safe way to cache across requests):

```bash
REDIS_URL=redis://localhost:6379/0 \
  uv run uvicorn examples.reactive_todo.app:app --reload
```

Redis backend: `pyjinhx.integrations.redis.RedisInvalidationBackend` (`pip install pyjinhx[redis]`).
