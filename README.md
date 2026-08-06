# PyJinHx

[![Pydantic](https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Jinja](https://img.shields.io/badge/Jinja-B41717?logo=jinja&logoColor=white)](https://jinja.palletsprojects.com/)
[![HTMX](https://img.shields.io/badge/HTMX-3366CC?logo=htmx&logoColor=white)](https://htmx.org/)

Type-safe UI components for Python web apps. A component is a Pydantic model plus a Jinja template sitting next to it — nest them with PascalCase tags, and co-located JS/CSS is collected automatically at render.

```bash
pip install pyjinhx
```

## Example

A `Card` that renders a `Button` — the tag's attributes become validated Pydantic fields:

```python
# components/button.py
from pyjinhx import BaseComponent


class Button(BaseComponent):
    id: str
    text: str
    variant: str = "default"
```

```html
<!-- components/button.pjx -->
<button id="{{ id }}" class="btn btn-{{ variant }}">{{ text }}</button>
```

```html
<!-- components/card.pjx -->
<div id="{{ id }}" class="card">
  <h2>{{ title }}</h2>
  <Button id="cta" text="{{ button_text }}" variant="primary"/>
</div>
```

```python
# components/card.py
from pyjinhx import BaseComponent, setup


class Card(BaseComponent):
    id: str
    title: str
    button_text: str = "Sign up"


setup(components_root="./components")
html = Card(id="hero", title="Get Started").render()
```

Drop a `button.css` or `card.js` next to the component and it's included once, automatically.

## Performance

**In plain terms:** for a typical page — a few dozen to a few hundred components, ordinary-sized text/JSON fields — rendering costs a fraction of a millisecond and stays that way as the page grows. The only scenarios below that get expensive are deliberately extreme ones (thousands of components on one page, or a single component holding tens of kilobytes of text) — see the "what this means for a real app" note under each table that has one.

- **Linear component-count scaling**: ~0.03 ms/component, flat from 50 to 10,000 components in a tree — no super-linear blowup from breadth.
- **Flat nesting-depth cost**: ~0.4 ms/level regardless of chain length (10 to 160 levels deep).
- **No static/reactive mixing penalty**: a tree with some `ReactiveComponent` levels and some plain ones costs the same as an all-reactive tree of the same shape — noise-level delta at every size.
- **Cross-request caching, when configured, turns a repeat render into ~0.3 ms** regardless of how expensive the underlying data lookup is — see "Cross-request caching" below.
- **Fan-out re-renders thread I/O-bound work automatically** (2-7.6x faster for realistic database-style costs) and stay at parity — no threading tax — when there's nothing to overlap.

Run via `uv run python scripts/bench_*.py` on `origin/master`, single machine, no averaging across runs — directional, not authoritative. Add `PJX_BENCH_PROFILE=1` before any of them for a full `cProfile` breakdown of where the time actually goes. Full numbers below:

<details>
<summary>Full benchmark tables</summary>

### Component count scaling (`bench_render_scaling_v2.py`)

**What it measures:** how render time grows as a page gets more components on it — the most direct "will this scale" question.

Renders one nested tree per data point — a fixed 3-level shape (root → mids → leaves), with breadth scaled so the total component count hits the target `n`. This is the shape a real page has: a few structural layers, many repeated leaves.

```
          BenchRoot
         /    |    \
     Mid1   Mid2  ... Midk
     /  \    /  \
  Leaf  Leaf Leaf  Leaf  ...
```

| components on the page | total render time | ms per component |
|---|---|---|
| 50 | 1.7 ms | 0.035 |
| 100 | 3.3 ms | 0.033 |
| 197 | 6.1 ms | 0.031 |
| 507 | 15.8 ms | 0.031 |
| 993 | 30.1 ms | 0.030 |
| 1,981 | 60.3 ms | 0.030 |
| 4,971 | 149.1 ms | 0.030 |
| 10,000 | 293.1 ms | 0.029 |

**What this means for a real app:** the "ms per component" column barely moves as the page grows from 50 components to 10,000 — there's no penalty for a bigger page beyond the components it actually adds. A typical page (tens to low hundreds of components) renders in low single-digit milliseconds.

### Nesting depth scaling (`bench_render_depth.py`)

**What it measures:** whether deeply nested components (a component inside a component inside a component...) cost more per level than a shallow, wide page does.

Breadth pinned at 1 — a single linear chain, no siblings — with depth swept instead. Isolates any cost that scales with *nesting depth* specifically (recursive fill/serialize, the ancestor-chain cycle guard, scope propagation through nested renders), which the component-count sweep above can't see since it holds depth fixed at 3.

```
Root → Level1 → Level2 → Level3 → ... → LevelN
```

| nesting depth | total render time | ms per level |
|---|---|---|
| 10 | 4.14 ms | 0.414 |
| 20 | 8.27 ms | 0.414 |
| 40 | 16.30 ms | 0.407 |
| 80 | 33.16 ms | 0.414 |
| 160 | 61.18 ms | 0.382 |

**What this means for a real app:** ms/level stays flat out to 160 levels deep — a chain far deeper than any real component tree — so nesting depth on its own is never the bottleneck.

### Field count scaling, 200 children per tree (`bench_field_count.py`)

**What it measures:** the cost of a component having many fields (validated Pydantic attributes), and specifically the extra cost when some of those fields carry JSON-looking strings that need parsing.

Tree shape pinned; declared field *count* per component swept instead. Two arms per field count:

- **plain** — every field is `str`, coercion takes the cheap early-out.
- **json** — every field is `list` with a JSON-looking string value, so every field goes through `json.loads`.

| fields per component | plain fields | JSON-valued fields | us per child (JSON arm) |
|---|---|---|---|
| 5 | 6.66 ms | 8.79 ms | 44.0 |
| 20 | 10.02 ms | 15.28 ms | 76.4 |
| 50 | 17.13 ms | 29.02 ms | 145.1 |
| 100 | 30.10 ms | 54.07 ms | 270.4 |

**What this means for a real app:** cost grows in a straight line with field count, no sudden jump — a component with a normal number of fields (a handful to a couple dozen) pays a small, predictable tax even in the worst case (every field is JSON).

### Slot payload size, 50 components per tree (`bench_slot_payload.py`)

**What it measures:** what happens when a component's content is *large* (a long piece of text or a big JSON blob) rather than many small fields — this is the one place render time is genuinely driven by content size, not component count.

Component count pinned; payload *size in bytes* swept instead. Two arms:

- **children** — payload rides in as a tag's body text (children-field merge).
- **slot** — payload rides in as a list of leaf component instances on a `Slot` field.

| payload size | children arm | slot arm | us per KB (children arm) |
|---|---|---|---|
| 64 bytes | 2.50 ms | 1.82 ms | 799.5 |
| 256 bytes | 5.58 ms | 3.45 ms | 446.3 |
| 1 KB | 17.47 ms | 9.40 ms | 349.5 |
| 4 KB | 65.54 ms | 33.84 ms | 327.7 |
| 16 KB | 261.29 ms | 132.73 ms | 326.6 |
| 64 KB | 1,080.34 ms | 549.51 ms | 337.6 |

Those totals are for **50 components at once**; per single component, a 64 KB payload costs roughly **20 ms** (measured directly, not divided out — a 64 KB payload is about 800-1,300 lines of plain text, well beyond a typical field's content).

**What this means for a real app:** this only matters if a single component's field holds tens of kilobytes of text or JSON — a label, a description, a normal-sized JSON payload for a form (well under 1 KB) costs a fraction of a millisecond. This is the one benchmark in this whole suite where the answer is "yes, be mindful of it," but only for genuinely large content in one field, not for ordinary component usage. ([Tracked as a known, unfixed edge case — issue #907](https://github.com/paulomtts/pyjinhx/issues/907).)

### Mixed static/reactive tree, identical node counts (`bench_mixed_reactive_tree.py`)

**What it measures:** whether mixing `ReactiveComponent` (data-backed, cache-aware) and plain `BaseComponent` levels in the same tree costs more than an all-one-kind tree of the same size.

Same tree shape and node count in both arms — only which levels are reactive changes.

```
mixed:                       pure:
  [static Root]                [reactive Root]
        |                            |
  [static Mid] ...             [reactive Mid] ...
        |                            |
  [reactive Leaf] ...           [reactive Leaf] ...
```

| nodes in tree | mixed (some static) | pure (all reactive) | difference |
|---|---|---|---|
| 56 | 3.61 ms | 3.64 ms | +0.03 ms |
| 211 | 11.86 ms | 11.82 ms | -0.04 ms |
| 821 | 42.70 ms | 43.31 ms | +0.61 ms |
| 1,831 | 93.72 ms | 91.02 ms | -2.70 ms |

**What this means for a real app:** the difference bounces around zero at every size — there's no cost to having a mix of reactive and static components on the same page; only how many components you have matters, not the ratio.

### `state_hash()` cost (`bench_state_hash.py`)

**What it measures:** the cost of computing a reactive component's content fingerprint (used to detect "did this actually change" before sending an update to the browser) — called directly here, isolated from a full render, so a regression in the hash itself isn't hidden by other costs.

Two things move this cost independently: how many fields a component has, and how big each field's value is.

By field count (16-byte values):

| fields | microseconds per call | microseconds per field |
|---|---|---|
| 5 | 3.33 | 0.666 |
| 20 | 6.16 | 0.308 |
| 50 | 11.88 | 0.238 |
| 100 | 19.87 | 0.199 |

By value size (10 fields, value size swept):

| value size | microseconds per call | microseconds per KB |
|---|---|---|
| 16 bytes | 4.23 | 27.09 |
| 256 bytes | 8.58 | 3.43 |
| 4 KB | 81.38 | 2.03 |
| 64 KB | 1,514.88 | 2.37 |

**What this means for a real app:** microseconds, not milliseconds, for any realistic component — this cost is invisible next to an actual render.

### Load-cache indexing cost (`bench_reactive_cache.py`)

**What it measures:** the bookkeeping cost of the in-memory, per-request cache that avoids re-fetching the same data twice in one request — separate from the fetch itself, just the cache's own indexing work.

| entries cached | add one | re-add (already present) | clear everything |
|---|---|---|---|
| 500 | 0.41 ms | 0.54 ms | 0.11 ms |
| 1,000 | 0.87 ms | 0.85 ms | 0.23 ms |
| 2,000 | 2.01 ms | 1.91 ms | 0.55 ms |
| 4,000 | 3.35 ms | 3.81 ms | 1.24 ms |
| 8,000 | 8.46 ms | 9.38 ms | 2.98 ms |

**What this means for a real app:** doubling the number of cached entries roughly doubles the cost, not more — no hidden quadratic blowup even with thousands of cached items in one request.

### Cross-request caching (`bench_cross_request_cache.py`, `bench_cross_request_load.py`)

**What it measures:** the payoff of configuring a `CacheBackend` (e.g. `pyjinhx[diskcache]`) so a component's data survives *across* requests, not just within one. Without a backend configured, this is entirely opt-in — nothing below applies unless you turn it on.

Without a backend, a fresh request always re-renders and re-fetches from scratch (no regression to watch here — this confirms "no backend" behaves exactly as before):

| components on the page | first request | later requests |
|---|---|---|
| 50 | 3.8 ms | 1.6 ms |
| 197 | 5.7 ms | 5.8 ms |
| 993 | 31.1 ms | 29.5 ms |
| 4,971 | 141.7 ms | 142.4 ms |

With a backend configured, the real win shows up on the *data-fetch* side — sweeping how expensive a simulated database call inside `load()` is, with and without the cache:

| simulated database cost | no backend | with `diskcache` backend | time saved |
|---|---|---|---|
| 0 ms (in-memory only) | 0.15 ms | 0.29 ms | — (cache overhead exceeds a no-op fetch) |
| 0.1 ms | 3.19 ms | 0.30 ms | 91% |
| 0.5 ms | 11.15 ms | 0.29 ms | 97% |
| 2.0 ms | 41.35 ms | 0.29 ms | 99% |
| 10.0 ms | 202.63 ms | 0.28 ms | 100% |

**What this means for a real app:** once a database call or API request costs even a fraction of a millisecond — which almost any real one does — cross-request caching turns a repeat page load into a flat ~0.3 ms regardless of how expensive the original fetch was. The only case where it doesn't help is data that was already effectively free to fetch (pure in-memory, no I/O at all).

### Reactive fan-out (`bench_reactive_fanout.py`)

This is the machinery that runs *after* a mutation — deciding which of the client's currently-mounted components need updating and re-rendering just those, rather than the whole page.

**Load-cache memoization** — one instance, cold call (real `load()`) vs. warm call (cache hit): cold 68.8 us, warm 12.0 us.

**`walk_manifest()`** — scanning the client's mounted components to find which ones changed. Cost is driven by "how many components the client currently has on screen," not by the size of the render that just happened. Swept over manifest size at three "how much changed" shares:

| components on screen | nothing changed | half changed | everything changed |
|---|---|---|---|
| 50 | 0.20 ms | 4.89 ms | 2.48 ms |
| 100 | 0.33 ms | 2.99 ms | 5.42 ms |
| 200 | 0.64 ms | 5.09 ms | 9.94 ms |
| 500 | 1.67 ms | 15.95 ms | 28.47 ms |
| 1,000 | 3.88 ms | 24.49 ms | 45.25 ms |
| 2,000 | 6.80 ms | 48.56 ms | 90.99 ms |
| 5,000 | 17.71 ms | 126.42 ms | 241.53 ms |

**What this means for a real app:** cost is driven almost entirely by how much actually changed, not by how many components are on screen — the "nothing changed" column stays cheap even with 5,000 components mounted. A typical mutation changes a handful of components, not thousands.

**Building the update (concurrent vs. one-at-a-time)** — when a changed component's data fetch is I/O-bound (a real database call), pyjinhx automatically runs those fetches concurrently instead of one after another. Measured at steady state (after each component class's fetch cost has been measured once):

| simulated database cost | 8 changed components | 32 changed components |
|---|---|---|
| 0 ms (in-memory only) | 1.0x (no difference) | 1.0x (no difference) |
| 0.5 ms | 2.0x faster | 3.5-4.1x faster |
| 2.0 ms | 3.9-4.0x faster | 5.6-6.0x faster |
| 10.0 ms | 6.2-6.8x faster | 7.6x faster |

**What this means for a real app:** for realistic database-backed components, updating many changed regions at once is multiple times faster than one-at-a-time — and for components with no real I/O cost, pyjinhx correctly doesn't bother threading them, so there's no overhead tax either way. (Note: pyjinhx decides this once per component class and remembers it for the life of the process, so a class whose fetch cost changes dramatically over time — fast at startup, slow once a database is under load — can be slower to adapt; [tracked in issue #906](https://github.com/paulomtts/pyjinhx/issues/906).)

**Building the response body** — per changed component, stamping the swap instruction and serializing its HTML. Swept over how many regions changed × how fragmented each region's markup is:

```
region 1: [piece][piece][piece] ...  (× pieces per region)
region 2: [piece][piece][piece] ...
   ...    × number of regions
```

| regions changed | 1 piece each | 10 pieces each | 50 pieces each |
|---|---|---|---|
| 10 | 0.24 ms | 0.07 ms | 0.14 ms |
| 50 | 0.20 ms | 0.29 ms | 0.61 ms |
| 100 | 0.40 ms | 0.55 ms | 1.30 ms |
| 200 | 0.78 ms | 1.07 ms | 2.64 ms |

**Skipping redundant work** — when a changed component is nested inside another changed component, pyjinhx skips re-sending the nested one (the parent's update already covers it). Swept by how large each candidate's rendered content is:

| content size per candidate | 50 candidates | 200 candidates |
|---|---|---|
| 1 unit | 0.03 ms | 0.13 ms |
| 10 units | 0.11 ms | 0.43 ms |
| 50 units | 0.43 ms | 1.75 ms |
| 200 units | 1.53 ms | 5.93 ms |

</details>

## Reactivity (HTMX)

Components declare what state they depend on. Return one component from a mutation route — every other mounted region that reacts to the same keys updates via out-of-band swaps, no manual wiring:

```python
from pyjinhx import ReactiveComponent, MutationKey, mutates, setup


class Keys(MutationKey):
    TODOS = "todos"


class Counter(ReactiveComponent, react={Keys.TODOS}):
    remaining: int

    @classmethod
    def load(cls) -> "Counter":
        return cls(remaining=db.remaining())


@mutates(Keys.TODOS)
def toggle_all():
    db.toggle_all()


setup(app)  # FastAPI: lifespan + middleware, done


@app.post("/todos/toggle")
def toggle():
    toggle_all()
    return Counter.render()  # other regions reacting to TODOS update too
```

## Learn more

- [Usage tiers](docs/guide/usage-tiers.md) — adopt only the layers you need
- [Components](docs/guide/components.md) · [PascalCase tags](docs/guide/tags.md) · [Assets](docs/guide/assets.md)
- [Reactivity guide](docs/reactivity.md)
- [Built-in components](docs/components.md)
