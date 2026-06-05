# Reactivity (Dependency-Aware OOB Swaps)

pyjinhx owns **composition**; HTMX owns **transport and swap**. Between them sits
the **state→view dependency graph** — which regions must change when a piece of
state changes. pyjinhx lets you declare that graph once, on the components, so a
mutation route re-emits exactly the mounted regions that depend on what changed.

A region that depends on a dirtied key is reloaded and re-emitted **only when its
value actually changed** — its freshly computed `state_hash()` is compared against
the hash the client reported, and a matching hash is skipped. (`render()`
integration and a `load()` cache are planned follow-ups.)

## 1. Make a component reactive

A component is reactive when it declares `depends_on` and a `load()` classmethod:

```python
from typing import ClassVar
from pyjinhx import BaseComponent

class Counter(BaseComponent):
    remaining: int
    depends_on: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "Counter":
        return cls(id="counter", remaining=db.remaining())
```

- `depends_on` — the named state keys this component derives from.
- `load()` — rebuilds the component from the current world, independent of any route.
- `state_hash()` is provided by `BaseComponent` (hash of `model_dump_json()`); override only for custom hashing.

Reactive components are stamped with `data-pjx-id`, `data-pjx-type` (the class
name), and `data-pjx-hash` on their root element automatically.

## 2. Ship the client runtime

Subclass `Layout` for your page shell — the manifest runtime is injected once on
full-page renders:

```python
from pyjinhx import Layout

class AppShell(Layout):
    ...  # app_shell.html is your full page template
```

Or, in a raw Jinja layout, drop in `client_script()`:

```python
from pyjinhx import client_script

# in your template context
{"pjx_runtime": client_script()}
```
```html
<body>
  ...
  {{ pjx_runtime }}
</body>
```

The runtime attaches a manifest of mounted regions to every htmx request via the
`X-PJX-Mounted` header.

## 3. Emit OOB swaps from your route

Build the primary response from the mutation result and call `render()` with what
you dirtied plus the incoming request — the dependent regions ride along as
out-of-band swaps:

```python
@app.post("/todos/{id}/toggle")
def toggle(id, request):
    db.toggle(id)
    return TodoItem(id=id, text=..., done=...).render(
        dirtied={"todos"},
        mounted=request,
    )
```

`render(dirtied=, mounted=)` renders the component itself as the primary response,
then appends an OOB swap for every *other* mounted reactive region whose
`depends_on` intersects `dirtied`, rebuilding each via its own `load()`. The
component's own region is never double-swapped.

`mounted` accepts a request-like object (the `X-PJX-Mounted` header is read off it
without importing any web framework), the raw header string, an already-parsed
list, or `None`. With neither `dirtied` nor `mounted`, `render()` is an ordinary
plain render.

### Lower-level: `oob_swaps()`

If you need the swaps without a primary (or want to compose them yourself), call
`oob_swaps(dirtied, mounted)` directly — it returns the concatenated `hx-swap-oob`
fragments (this is exactly what `render()` delegates to, passing
`exclude_ids={self.id}`):

```python
from pyjinhx import oob_swaps

swaps = oob_swaps(dirtied={"todos"}, mounted=request)
```

`oob_swaps`:
- keeps only mounted regions whose `depends_on` intersects `dirtied`,
- calls each region's `load()` and re-renders it,
- skips a region whose freshly computed `state_hash()` matches the hash the client
  reported (its DOM value is already current); a missing or mismatched hash always
  swaps — *when in doubt, swap*,
- drops any region nested inside another swapped region (the parent already contains it),
- returns concatenated `hx-swap-oob` fragments (empty if nothing changed).

The dependency graph lives in exactly one place — the `depends_on` declarations —
not smeared across endpoints. Adding a progress bar that declares
`depends_on = {"todos"}` makes it participate automatically; no endpoint changes.

## Boundaries

- **Hash gating is a skip-hint, not correctness authority**: a matching client hash
  earns permission to skip; missing/unknown/mismatched always swaps. It saves
  bandwidth and DOM churn, not database work (a short-circuiting `load()` cache is a
  later phase).
- **Type-singleton**: one mounted instance per reactive type is reloaded; instance-keyed deps (`"user:42"`) are deferred.
- **`mounted` accepts** a request-like object (header duck-typed out, no framework import), the raw header string, a parsed list, or `None`.
- **`load()` is zero-arg in v1** (type-singleton). Reactive `render()` auto-`load()`s dependents; you never call `load()` yourself for a reactive render.
