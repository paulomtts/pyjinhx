# How pyjinhx works — the runtime in five diagrams

A high-level tour of the request round trip, the render walk, the two composition
forms, the caches, and reactivity. *Living* — where this and reality disagree, fix
the doc.

Published as an artifact: <https://claude.ai/code/artifact/b9e2deec-951e-4c27-82a6-f7c0de56d9b9>

## 1. The round trip

One handler return becomes one response. Everything pyjinhx does happens between
those two points, inside a request scope.

```mermaid
flowchart TD
  A["HTTP request"] --> B["request_scope&lpar;&rpar;<br/>ContextVar spine"]
  B --> C["your handler"]
  C --> D{"what did it return?"}
  D -->|component| E["render&lpar;&rpar;"]
  D -->|str / __html__| F["use as-is"]
  D -->|None| G["empty primary"]
  D -->|anything else| H["PASSTHROUGH<br/>framework keeps it"]
  E --> I["primary markup"]
  F --> I
  G --> I
  I --> J["fan-out<br/>attach OOB legs"]
  J --> K["PjxResponse<br/>body + htmx headers"]
```

`responses.py` · `compose()` → `_fan_out()`

## 2. Inside one render

`render_level()` is the single recursive path. Every component — page, shell, leaf
— goes through the same gates.

```mermaid
flowchart TD
  S["render_level&lpar;component&rpar;"] --> CY{"same class 32x<br/>on this path?"}
  CY -->|yes| ERR["ValueError: cycle"]
  CY -->|no| RC{"render cache eligible?"}
  RC -->|"reactive class"| OFF["no cache —<br/>renders every time"]
  RC -->|"too cheap to cache"| OFF
  RC -->|"holds slot components"| OFF
  RC -->|eligible| LOOK{"cache hit?"}
  LOOK -->|hit| REST["restore shell segments<br/>child holes stay holes"]
  LOOK -->|miss| PARSE
  OFF --> PARSE["render template once<br/>split into segments"]
  PARSE --> FILL["for each child hole"]
  REST --> FILL
  FILL --> REC["render_level&lpar;child&rpar;"]
  REC -.recurse.-> S
  FILL --> OUT["RenderedLevel<br/>children as objects, not text"]
```

`rendering.py` · `render_level()` · `_finish_cached_level()` · `_fill_children()`

A cache hit restores *only the shell*. Children are still holes, so they resolve
and recurse exactly as on a fresh render. Measured on a cacheable `Shell`
containing `<Leaf/>`:

```text
render #1  templates built: ['Shell', 'Leaf']
render #2  templates built: ['Leaf']
render #3  templates built: ['Leaf']
```

## 3. Two ways a child gets in

This distinction drives most of the runtime's behaviour — and most of its sharp
edges.

```mermaid
flowchart TD
  subgraph TAG["TAG composition"]
    T1["Shell.load&lpar;&rpar; → shell"] --> T2["template says &lt;Child /&gt;"]
    T2 --> T3["ChildRef — a HOLE"]
    T3 --> T4["renderer resolves class<br/>binds props → key"]
    T4 --> T5["Child.load&lpar;&rpar; runs here"]
  end
  subgraph SLOT["SLOT composition"]
    S1["Shell.load&lpar;&rpar; builds the child<br/>in Python"] --> S2["content = Child&lpar;already loaded&rpar;"]
    S2 --> S3["no hole — it is data"]
    S3 --> S4["renderer just interpolates it"]
  end
```

**Tag → a hole.** The child is a reference until render time. The runtime knows
its class and its key before it loads, so it can decide what to do with it.

**Slot → already data.** The child is a fully-loaded instance living inside the
parent's return value. There is no decision point left, because there is nothing
to decide about.

## 4. The caches

Two independent stores. A component uses one or the other, never both — and
**neither one ever caches a subtree.** Both stop at the component boundary.

```mermaid
flowchart LR
  subgraph L["LOAD CACHE — reactive classes"]
    direction TB
    L0["Component.load&lpar;key&rpar;"] --> L1{"tier 1<br/>request dict"}
    L1 -->|hit| LH["return"]
    L1 -->|miss| L2{"tier 2<br/>cross-request backend"}
    L2 -->|hit| LH
    L2 -->|miss| L3["run load&lpar;&rpar; body"]
    L3 --> LH
  end
  subgraph R["RENDER CACHE — plain classes"]
    direction TB
    R0["render_level"] --> R1{"backend hit?"}
    R1 -->|hit| R2["restore shell only"]
    R1 -->|miss| R3["render template"]
  end
```

| | stores | children |
|---|---|---|
| **Load cache** | the instance `load()` returned; the cache key *is* the load key | not in it |
| **Render cache** | that component's own shell segments | still holes |

Because neither store holds a composed subtree, a hit can never short-circuit the
descent: there is no cached artifact containing the children, so the renderer must
go and get them.

## 5. Reactivity

Components declare keys. A mutation dirties keys. Everything downstream is that one
match.

```mermaid
sequenceDiagram
  autonumber
  participant C as client
  participant H as handler
  participant K as dirtied keys
  participant X as caches
  participant F as fan-out
  C->>H: htmx request
  H->>K: mutation marks "todos" dirty
  H-->>F: returns primary component
  K->>X: invalidate&lpar;dirtied&rpar; — both tiers
  F->>F: walk client manifest
  F->>F: keep regions whose keys were dirtied
  F->>F: preserve nested regions that were not
  F-->>C: primary + OOB fragments
```

`reactive/cache.py` · `reactive/fanout.py` · `responses.py`

**What keys decide:** which cache entries get evicted, and which client regions get
swapped out-of-band.

**What they don't:** which `load()` bodies actually run. That is decided by cache
residency and by position in the render tree — `get_dirtied()` is read in exactly
one production path (`responses.py:61`), which runs *after* the primary render.

## 6. Where the model leaks

| Intent | Status | What actually happens |
|---|---|---|
| A parent's `load()` never triggers a child's | literally true | No `load()` calls another. But the *renderer* does, at full depth — and a cache hit does not stop it, because no cache holds a subtree. |
| Reactivity follows declared keys | for swaps | True for eviction and for OOB region selection. Not true for which loads execute. |
| A cached shell serves fresh children | tags ✓ slots ✗ | Tag children re-resolve through their holes. Slot children are frozen inside the parent's cached value and never reload. |

The common thread: the runtime knows each parent→child edge at the moment it fills
a hole, but never records it — so anything needing that edge later has to re-derive
it, or fails.

The fix is specified in
[`../specs/2026-08-25-nested-freshness-design.md`](../specs/2026-08-25-nested-freshness-design.md).
