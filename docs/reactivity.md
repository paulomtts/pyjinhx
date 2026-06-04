# Reactivity (Dependency-Aware OOB Swaps)

pyjinhx owns **composition**; HTMX owns **transport and swap**. Between them sits
the **state→view dependency graph** — which regions must change when a piece of
state changes. pyjinhx lets you declare that graph once, on the components, so a
mutation route re-emits exactly the mounted regions that depend on what changed.

This is the **always-swap baseline**: every region that depends on a dirtied key
is reloaded and swapped. (Hash-gating to skip unchanged regions, `render()`
integration, and a `load()` cache are planned follow-ups.)

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

In a mutation route, render your primary response as usual, then append the OOB
swaps for everything that depends on what you changed:

```python
from pyjinhx import oob_swaps, PJX_MOUNTED_HEADER

@app.post("/todos/{id}/toggle")
def toggle(id, request):
    db.toggle(id)
    primary = TodoItem(id=id, text=..., done=...).render()
    swaps = oob_swaps(
        dirtied={"todos"},
        mounted=request.headers.get(PJX_MOUNTED_HEADER, ""),
    )
    return primary + swaps
```

`oob_swaps`:
- keeps only mounted regions whose `depends_on` intersects `dirtied`,
- calls each region's `load()` and re-renders it,
- drops any region nested inside another swapped region (the parent already contains it),
- returns concatenated `hx-swap-oob` fragments (empty if nothing matched).

The dependency graph lives in exactly one place — the `depends_on` declarations —
not smeared across endpoints. Adding a progress bar that declares
`depends_on = {"todos"}` makes it participate automatically; no endpoint changes.

## Boundaries (current baseline)

- **Always-swap**: hash-gating is not applied yet — a matching region is always re-sent.
- **Type-singleton**: one mounted instance per reactive type is reloaded; instance-keyed deps (`"user:42"`) are deferred.
- **`mounted` accepts** the raw header string, a parsed list, or `None`. Passing a request object directly arrives with `render()` integration.
