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
<!-- components/button.html -->
<button id="{{ id }}" class="btn btn-{{ variant }}">{{ text }}</button>
```

```html
<!-- components/card.html -->
<div id="{{ id }}" class="card">
  <h2>{{ title }}</h2>
  <Button id="cta" text="{{ button_text }}" variant="primary"/>
</div>
```

```python
# components/card.py
from pyjinhx import BaseComponent, Renderer


class Card(BaseComponent):
    id: str
    title: str
    button_text: str = "Sign up"


Renderer.set_default_environment("./components")
html = Card(id="hero", title="Get Started").render()
```

Drop a `button.css` or `card.js` next to the component and it's included once, automatically.

## Performance

- **Linear component-count scaling**: ~0.03 ms/component, flat from 50 to 10,000 components in a tree — no super-linear blowup from breadth.
- **Flat nesting-depth cost**: ~0.4 ms/level regardless of chain length (10 to 160 levels deep).
- **No static/reactive mixing penalty**: a tree with some `ReactiveComponent` levels and some plain ones costs the same as an all-reactive tree of the same shape — noise-level delta at every size.

Run via `uv run python scripts/bench_*.py` on `origin/master`, single machine, no averaging across runs — directional, not authoritative. Full numbers, including field-count, slot-payload-size, and reactive-fanout sweeps:

<details>
<summary>Full benchmark tables</summary>

### Component count scaling (`bench_render_scaling_v2.py`)

Renders one nested tree per data point — a fixed 3-level shape (root → mids → leaves), with breadth scaled so the total component count hits the target `n`. This is the shape a real page has: a few structural layers, many repeated leaves.

```
          BenchRoot
         /    |    \
     Mid1   Mid2  ... Midk
     /  \    /  \
  Leaf  Leaf Leaf  Leaf  ...
```

| n | total | ms/component |
|---|---|---|
| 50 | 1.7 ms | 0.034 |
| 100 | 3.2 ms | 0.032 |
| 197 | 6.1 ms | 0.031 |
| 507 | 15.2 ms | 0.030 |
| 993 | 29.6 ms | 0.030 |
| 1981 | 58.3 ms | 0.029 |
| 4971 | 142.2 ms | 0.029 |
| 10000 | 283.8 ms | 0.028 |

ms/component holds flat (even trends slightly down) as the tree grows — no super-linear blowup from breadth.

### Nesting depth scaling (`bench_render_depth.py`)

Breadth pinned at 1 — a single linear chain, no siblings — with depth swept instead. Isolates any cost that scales with *nesting depth* specifically (recursive fill/serialize, the ancestor-chain cycle guard, scope propagation through nested renders), which the component-count sweep above can't see since it holds depth fixed at 3.

```
Root → Level1 → Level2 → Level3 → ... → LevelN
```

| depth | total | ms/level |
|---|---|---|
| 10 | 3.95 ms | 0.395 |
| 20 | 7.68 ms | 0.384 |
| 40 | 15.28 ms | 0.382 |
| 80 | 32.26 ms | 0.403 |
| 160 | 64.48 ms | 0.403 |

ms/level is flat — depth alone doesn't cost more per level as the chain gets longer.

### Field count scaling, 200 children/tree (`bench_field_count.py`)

Tree shape pinned; declared field *count* per component swept instead. Targets two costs that scale with field count specifically: the JSON-attr-coercion validator (loops over every field on each instantiation) and child-attr copying. Two arms per field count:

- **plain** — every field is `str`, coercion takes the cheap early-out.
- **json** — every field is `list` with a JSON-looking string value, so every field goes through `json.loads`.

| fields | plain | json | us/child (json) |
|---|---|---|---|
| 5 | 6.91 ms | 9.61 ms | 48.1 |
| 20 | 10.64 ms | 18.40 ms | 92.0 |
| 50 | 17.54 ms | 34.85 ms | 174.3 |
| 100 | 30.91 ms | 81.72 ms | 408.6 |

JSON-coercion cost scales roughly linearly with field count, as expected — no quadratic surprise.

### Slot payload size, 50 components/tree (`bench_slot_payload.py`)

Component count pinned; payload *size in bytes* swept instead, to isolate costs that scale with byte count rather than component count (the segment parser scanning every character, and slot-placeholder splicing walking each string segment). Two arms:

- **children** — payload rides in as a tag's body text (children-field merge).
- **slot** — payload rides in as a list of leaf component instances on a `Slot` field, so the parent emits one placeholder token per leaf that must be found and replaced.

| bytes | children slot | plain slot | us/KB (children) |
|---|---|---|---|
| 64 | 2.48 ms | 1.72 ms | 794.53 |
| 256 | 6.15 ms | 3.48 ms | 492.15 |
| 1024 | 19.56 ms | 9.95 ms | 391.21 |
| 4096 | 78.22 ms | 37.48 ms | 391.09 |
| 16384 | 297.93 ms | 139.86 ms | 372.41 |
| 65536 | 1184.57 ms | 554.10 ms | 370.18 |

us/KB drops and then flattens as payload grows — fixed per-call overhead dominates at small sizes, byte-scanning cost dominates and stabilizes at larger ones.

### Mixed static/reactive tree, identical node counts (`bench_mixed_reactive_tree.py`)

Same tree shape and node count in both arms — only which levels are `ReactiveComponent` vs plain `BaseComponent` changes. Isolates the one place the two paths diverge: every child instantiation unconditionally calls `pjx_mount()`, a no-op on a plain component but a cache-routed `load()` on a reactive one.

```
mixed:                       pure:
  [static Root]                [reactive Root]
        |                            |
  [static Mid] ...             [reactive Mid] ...
        |                            |
  [reactive Leaf] ...           [reactive Leaf] ...
```

| nodes | mixed | pure reactive | delta |
|---|---|---|---|
| 56 | 2.26 ms | 2.21 ms | -0.05 ms |
| 211 | 8.00 ms | 7.78 ms | -0.22 ms |
| 821 | 28.73 ms | 29.69 ms | +0.96 ms |
| 1831 | 66.75 ms | 65.29 ms | -1.46 ms |

No consistent overhead from mixing static and reactive components in the same tree — noise-level delta at every size, meaning a page's reactive *share* isn't a meaningful cost driver on its own.

### state_hash() cost (`bench_state_hash.py`)

Calls `state_hash()` directly in a loop — no session, no render — since inside a full render it's normally dwarfed by `load()` and `render_level()`, hiding any regression in the hash itself. `state_hash()` is three stacked costs: `model_dump(mode="json")`, a sorted `json.dumps`, and a SHA-256 digest. Two axes swept independently:

By field count (16-byte values — moves `model_dump`'s per-field work and the number of keys `json.dumps` sorts):

| fields | us/call | us/field |
|---|---|---|
| 5 | 3.66 | 0.733 |
| 20 | 6.96 | 0.348 |
| 50 | 13.28 | 0.266 |
| 100 | 21.22 | 0.212 |

By value size (10 fields, byte size swept — moves the encoded byte count `json.dumps`/SHA-256 consume, field count held constant):

| bytes | us/call | us/KB |
|---|---|---|
| 16 | 4.54 | 29.03 |
| 256 | 9.19 | 3.67 |
| 4096 | 78.38 | 1.96 |
| 65536 | 1544.74 | 2.41 |

### Load-cache indexing cost (`bench_reactive_cache.py`)

Isolates `cache_put()`/`invalidate()`'s index bookkeeping (reverse/forward bucket maintenance) from the render path entirely — just N cache entries, indexed and then evicted. The check: doubling N should roughly double each column, not quadruple it (a prior bug made full eviction quadratic — PR #619/#600 fixed the related `_drop_nested` cost below).

| entries | put | re-put | invalidate all |
|---|---|---|---|
| 500 | 2.22 ms | 0.41 ms | 0.11 ms |
| 1000 | 0.81 ms | 0.84 ms | 0.24 ms |
| 2000 | 1.72 ms | 1.92 ms | 0.63 ms |
| 4000 | 3.45 ms | 4.05 ms | 1.15 ms |
| 8000 | 8.70 ms | 8.19 ms | 2.99 ms |

Roughly linear scaling holds (the 500-entry `put` row is a one-off warm-up outlier).

### Reactive fanout (`bench_reactive_fanout.py`)

Four sub-benchmarks over the machinery that runs *after* a render, driven by the client's mounted manifest rather than the tree just rendered:

**Load-cache memoization** — one instance, cold call (real `load()`) vs. warm call (cache hit): cold 18.7 us, warm 3.0 us.

**`walk_manifest()`** — cost scales with "how many components the client currently has mounted," not with the size of the render that just happened. A clean candidate costs one cache lookup; a dirty one costs a real `load()` + `render_level()` + `state_hash()`. Swept over manifest size at three dirty shares:

| n | 0% dirty | 50% dirty | 100% dirty |
|---|---|---|---|
| 50 | 0.15 ms | 2.29 ms | 2.45 ms |
| 100 | 0.25 ms | 2.82 ms | 4.33 ms |
| 200 | 0.55 ms | 4.55 ms | 8.51 ms |
| 500 | 1.23 ms | 11.03 ms | 20.24 ms |
| 1000 | 2.58 ms | 22.46 ms | 41.14 ms |
| 2000 | 5.14 ms | 43.75 ms | 83.14 ms |
| 5000 | 13.79 ms | 108.36 ms | 208.39 ms |

Cost is driven almost entirely by dirty share, not raw manifest size — the 0%-dirty column stays cheap even at n=5000.

**`oob_swaps()` alone** — the response-body build that runs after the walk: per dirty candidate, stamps `hx-swap-oob`/`data-pjx-hash` at the recorded span and serializes. Swept over region count × per-region "span" count (how many discontiguous markup pieces make up one region), with levels prebuilt so no render is in the timed frame:

```
region 1: [span][span][span] ...  (× spans-per-region)
region 2: [span][span][span] ...
   ...    × region count
```

| regions | 1 span | 10 spans | 50 spans |
|---|---|---|---|
| 10 | 0.23 ms | 0.07 ms | 0.14 ms |
| 50 | 0.21 ms | 0.29 ms | 0.65 ms |
| 100 | 0.40 ms | 0.56 ms | 1.31 ms |
| 200 | 0.80 ms | 1.11 ms | 2.65 ms |

**`_drop_nested()`** — the containment walk that drops a dirty candidate already covered by an ancestor's swap. The candidate-count axis was made linear by #600/#619; this sweeps the other axis, per-candidate rendered-subtree size:

| subtree size | 50 candidates | 200 candidates |
|---|---|---|
| 1 | 0.03 ms | 0.12 ms |
| 10 | 0.10 ms | 0.43 ms |
| 50 | 0.51 ms | 1.80 ms |
| 200 | 1.63 ms | 6.58 ms |

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
