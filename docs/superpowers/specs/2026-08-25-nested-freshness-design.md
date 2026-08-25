# Design: nested reactive freshness — resolve at the hole

**Date:** 2026-08-25
**Status:** Approved, pending implementation plan
**Issues:** #1022, #1026, #1027, #1028
**Breaking:** yes — lands additively in a 1.x minor, enforced in 2.0

## Problem

Three defects share one cause. The runtime knows each parent→child edge at the
moment it fills a child hole, and never acts on it there — so freshness and
skip decisions are either made too late or not at all.

### 1. Clean children still load

Island reactivity promises two savings. Fan-out delivers one: a region whose
declared keys were not dirtied never reaches the wire. The other is not built —
every clean component still runs `load()` on the server, renders its template,
and has the markup discarded by fan-out.

The reason is structural, not an oversight. `get_dirtied()` is read in exactly
one production path (`responses.py:61`, inside `_fan_out`), which runs *after*
the primary render. By the time anything asks what was dirtied, every `load()`
has already executed. Neither `rendering.py` nor `_wrap_load` reads it at all.

Measured on a five-level reactive chain, each level declaring its own key:

```
cold render                              loads: L0 L1 L2 L3 L4   (5)
L0 fully cached, descendants evicted     loads:    L1 L2 L3 L4   (4)
only 'key0' dirtied                      loads: L0               (1, all 5 asked)
no tier-2 backend, request 2, nothing dirtied
                                         loads: L0 L1 L2 L3 L4   (5)
```

Output is always correct. This is a missing optimization, not wrong data — but
it is the optimization the library's design intent was written around.

### 2a. Tag composition serves a stale load key

A child whose key flows through its parent's data inherits that parent's
staleness. Confirmed by repro:

```
dirtied 'conversation'; user moved from conversation 1 -> 2

A  baseline (parent reacts to 'view' only)   child.load called: ['1']  stale: True
B  child given cache=False                   child.load called: ['1']  stale: True
C  parent reacts to ('view','conversation')  child.load called: ['2']  stale: False
```

The child's entry *is* evicted and its body *does* run — against a key read off
a parent that was not evicted. Opting the child out of caching does not rescue
it; only widening the parent's react set does.

### 2b. Slot composition freezes the child entirely

When a parent builds its child in Python, the child is a fully-loaded instance
inside the parent's cached `load()` result. There is no hole, so there is no
decision point:

```
WITH a tier-2 load cache backend
   shell.load() ran : False
   child.load() keys: NEVER
   serves stale     : True

WITHOUT any backend (the default)
   shell.load() ran : True
   child.load() keys: ['2']
   serves stale     : False
```

`holds_spliced_components` does not cover this. It is a *render*-cache gate, and
a reactive class turns the render cache off at the first check
(`rendering.py:336`), so the slot gate three lines down is never evaluated for
the components that have this bug. The freeze is in the **load** cache.

ADR 0003 makes every component-typed field a slot structurally, so this surface
is every nested component built in Python — not an opt-in few.

## The shared cause

A cached parent's data decides what its children are: the child's **key** in tag
form, the child **itself** in slot form. Either way staleness propagates
downward and nothing checks it. And because nothing consults dirtiness during
the render walk, no child can be skipped.

## Decision

Make `_fill_children` the single freshness decision point, for tags and slots
alike, at the moment the hole is filled and before the child loads.

```
_fill_children reaches a child hole
   |- resolve class -> declared react keys
   |- bind props    -> load key value
   |- dirtied this request?  -- no --+- client manifest holds it? -- yes -> PRESERVE
   |                                 \- no ------------------------------> load
   \- yes -> parent served from cache?
               |- no  -> load (fresh props)
               \- yes -> raise (provenance error)
```

Two facts make this feasible without new plumbing:

- `session.pjx_mounted` is populated by middleware *before* the handler runs
  (`integrations/fastapi.py:213`, inside `request_scope`, before `call_next`),
  so a hole-time decision can already ask what the client holds.
- `_load_reactive_child` (`rendering.py:111`) already resolves the class, pulls
  the key attr out of the props, and coerces it to the field's declared type —
  all before `cls.load(**key_args)`. That line is the decision point.

No template scanner, no recorded edge map, no ancestor rollup. The parent→child
edge is consumed at the instant it exists and never stored, because nothing
downstream needs it.

## Section 1 — The Ref contract

`ReactiveComponent` gains one classmethod:

```python
class Shell(ReactiveComponent, react=("view",)):
    content: Child | None = None

    @classmethod
    def load(cls, view: str) -> "Shell":
        return cls(id="shell", content=Child.ref(conversation=view))
```

`Child.ref(**props)` returns a frozen `(class, props)` pair. It runs no
`load()`, touches no cache, holds no data — the Python spelling of what
`<Child conversation="…"/>` already produces as a `ChildRef` (`segments.py:12`).
Component-typed slot fields accept it alongside a real instance; those fields are
already detected structurally at registration (ADR 0003), which is where the
widening goes.

What ends up in the parent's cached value is the whole point:

```python
# eager — caches the child's DATA. This is 2b.
Shell(content=Child(conversation="1", body="messages-of-1"))

# ref — caches an INSTRUCTION. Re-decided every request.
Shell(content=Ref(Child, {"conversation": "1"}))
```

### Legal field values

| value | when | freshness | islands |
|---|---|---|---|
| `Child.ref(...)` | default, recommended | resolved at the hole | yes |
| bare `Child(...)` | works where it validates | resolved at the hole | yes |
| `Child.load(...)` | parent needs the data | eager, parent uncacheable | no |
| plain component | non-reactive child | no load, no staleness | n/a |

A bare constructor call is already an unloaded instance — `load()` is a separate
classmethod — so it gets the same treatment at the hole. It is accepted but not
documented as the way, because it fails on any class with a required
load-supplied field:

```
Messages  bare construct OK   -> Messages(conversation='1', body='', unread=0)
Invoice   bare construct FAILS -> ValidationError: total  Field required
```

That failure's obvious workaround is `Invoice.load(...)`, which silently costs
islands and parent cacheability. `ref()` records props rather than building a
model, so it works for both classes identically.

### The eager escape hatch

A parent that genuinely needs its child's data — to sort, filter, or decide
whether to include it — keeps writing `Child.load(...)` and declares the field
eager:

```python
from pyjinhx import Eager   # exported alongside PjxKey / Slot / Children

content: Annotated[Child | None, Eager()] = None
```

Two rules attach to it:

- **A `load()` result holding a loaded reactive instance is not tier-2
  cacheable.** This is what makes 2b's remaining surface correct instead of
  silently stale: the parent renders live every request, and the reason is
  visible in the annotation.
- **Assigning a loaded reactive instance to a non-eager slot field raises**, so
  forgetting `ref()` is a loud failure rather than a silent downgrade:

```
Shell (template: shell.pjx): field 'content' was assigned a loaded Child.
A slot child is resolved at render time — assign Child.ref(conversation=…)
instead. If this child must be loaded inside Shell.load() (you need its data
to sort or filter it), declare the field eager:
    content: Annotated[Child | None, Eager()] = None
```

`ref()` is reactive-only. A plain component in a slot has no `load()` and
therefore no freshness problem.

## Section 2 — The decision at the hole

### Constraint

`hx-preserve` is resolved by htmx through the incoming tag's plain `id`
(`getElementById`), not `data-pjx-id` (`fanout.py:825`). Preservation therefore
only lands for a region whose template root carries a stable authored id. And
`hx-preserve` is a no-op for an id the client does not already show — which for
a placeholder means shipping an empty element. **The manifest check is
mandatory, not an optimization.**

### The skip gate

Skip a child only on positive proof of all five conditions:

| # | condition | existing machinery |
|---|---|---|
| 1 | reactive class | `_pjx_key_field` |
| 2 | no declared key dirtied this request | `_keys_match_dirtied` |
| 3 | manifest holds this id, type, load key | `session.pjx_mounted` |
| 4 | root id is authored, not auto | `has_auto_id` |
| 5 | class opts in | `retain_across_parent_swaps` (default `True`) |

Four of five already exist. `retain_across_parent_swaps` is already the
per-class switch for this question in the OOB path; reusing it means one flag
governs preservation everywhere rather than two that can disagree. Its default
of `True` means existing components get islands without opting in.

Any failed condition falls back to loading and rendering, exactly as today —
the same conservative posture `_preserve_nested` takes: skip only on proof,
never on absence of evidence.

### What gets emitted

```html
<div id="messages" hx-preserve="true"></div>
```

One new requirement: manifest entries gain the region's **root tag name**, so the
placeholder matches the live element. `pjx.js` has it at mount time; an added
field, not a new mechanism.

### Consequences

- **Descendants are independent.** `walk_manifest` reads the client's manifest,
  not what was rendered, so a dirty grandchild under a skipped parent still gets
  its own OOB leg — and `_drop_nested` will not swallow it, because the skipped
  parent's placeholder does not contain it.
- **Cold loads are correct by construction.** Empty manifest → condition 3 fails
  everywhere → the whole tree loads. No special case.
- **Slots join here.** `_splice_slot_nodes` hands a `Ref` to the same gate a
  `ChildRef` goes through. This is the payoff of section 1.

## Section 3 — Provenance and the 2a error

### The stamp

`_wrap_load` already branches on `cache_has(...)`. Mark instances returned from
either tier with `_pjx_from_cache = True`. One assignment, one place — the only
new state in this design.

### The check

At the same hole, once the skip gate has decided the child must load:

```
child's declared key dirtied this request?
  \- yes -> was the parent that supplied these props served from cache?
              \- yes -> raise
```

`_fill_children` currently takes only the level; the parent component is threaded
through from `render_level`. Both call sites (`render_level` and
`_finish_cached_level`) already hold it.

### The message

```
Shell (template: shell.pjx): child Child reacts to 'conversation', which this
request dirtied — but Shell was served from the load cache, so the props it
passed down are from an earlier request and Child's key may be stale.

Shell's data determines which Child is shown, so Shell depends on
'conversation' too:
    class Shell(ReactiveComponent, react=("view", "conversation")):

If Shell genuinely does not depend on it, silence this for the class:
    trust_cached_props: ClassVar[bool] = True
```

### Why raise rather than repair

The repair — evict the parent, re-run its `load()` — is always correct and needs
no analysis, but it fires on every interaction in the exact shape this library is
built for (shell plus keyed region). The shell would reload every request: the
cascade section 2 exists to kill, reintroduced through the back door. Raising
costs nothing at runtime and states the true fact — the parent depends on that
key. Repro scenario C is that fix, and it already works today.

### Accepted false positive

A literal key (`<Leaf leaf="x"/>`) under a cached parent whose `leaf` was dirtied
has no data flow, and this rule raises anyway. Two filters were considered and
rejected as premature: a template scan (precise for tags, structurally blind to
refs) and a value-membership test against the parent's fields (covers both,
misses computed keys). Both are two mechanisms where one would do, for a case
that hardcodes an identity into markup. Ship the coarse rule and the ClassVar
opt-out; add a filter only if real code trips it.

### Blast radius

The check can only fire when a parent came from cache, which requires a tier-2
backend. The default configuration has none, so no default-configured app can
hit this — and the apps that can are exactly those silently serving stale data
today.

Refs get this for free: a `Ref` built inside a cached parent's `load()` carries
the same staleness as an interpolated tag attr, and the same stamp on the same
parent catches it. One rule, both composition forms.

## Section 4 — Migration

Five changes, in descending blast radius:

1. **A loaded reactive instance in a slot field raises.** Mechanical migration:
   `Child.load(x)` → `Child.ref(x)`. Where the parent needs the data, mark the
   field `Annotated[Child | None, Eager()]`.
2. **An `Eager` field makes its parent tier-2 uncacheable.** No error, a slower
   parent, and the reason visible in the annotation.
3. **The 2a provenance raise.** Unreachable without a tier-2 backend.
4. **Clean children stop running `load()`.** The real semantic break: any
   `load()` with side effects — a hit counter, a lazy write, an audit log —
   silently loses them. Needs a prominent migration note. `load()` is a read,
   and the runtime now holds authors to it.
5. **Manifest gains a root tag name.** An old client sending the old manifest
   fails condition 3, so those children load exactly as today. Graceful
   degradation, no version negotiation.

**Release order:** ship `ref()` and `Eager()` additively in a 1.x minor with no
enforcement so authors can migrate at their own pace; flip the raises and the
skip gate on in 2.0. One extra release turns a cliff into a ramp.

## Implementation phases

The release order in section 4 gives two natural plans. Each is independently
shippable and independently testable.

**Phase 1 — additive, 1.x minor. No behavior change.**

1. `Ref` type and `ReactiveComponent.ref()`.
2. Slot fields accept a `Ref`; `_splice_slot_nodes` resolves one through the
   same path a `ChildRef` takes.
3. `Eager()` annotation; a `load()` result holding a loaded reactive instance is
   not tier-2 cacheable.
4. `_pjx_from_cache` stamp in `_wrap_load`.
5. Manifest gains the root tag name; `pjx.js` emits it.

At the end of phase 1 every new spelling works, nothing raises, and no child is
skipped. 2b's staleness is already fixed for anyone who has migrated, because a
`Ref` cannot freeze.

**Phase 2 — enforcing, 2.0.**

6. The skip gate in `_fill_children`, all five conditions, plus the preserved
   placeholder.
7. The provenance raise and its `trust_cached_props` opt-out.
8. The raise on assigning a loaded reactive instance to a non-eager slot field.
9. Migration note for side-effecting `load()` bodies.

Phase 2 is where the invariant test flips from 4 descendant loads to 0.

## Section 5 — Testing

The existing scratchpad repros are the corpus: `repro_1026_full.py`,
`blindspot_slot.py`, `invariants.py`, `what_is_cached.py`.

**The invariant test, first and loudest.** The five-level chain, asserting the
original design intent: *no `load()` body runs for a child whose keys were clean
and whose region the client holds.* Currently 4 descendant loads; should become
0. The one test that fails today for the right reason.

Per mechanism:

- **Skip gate** — five tests, one per condition, each proving a failed condition
  falls back to loading. Conservative-by-default is tested as the default, not
  assumed.
- **Preserve output** — placeholder carries the authored id, `hx-preserve="true"`,
  and the manifest's root tag.
- **Cold load** — empty manifest, whole tree loads.
- **Descendant independence** — dirty grandchild under a skipped parent gets its
  own OOB leg and is not swallowed by `_drop_nested`.
- **Slot refs** — `blindspot_slot.py` inverted: child loads with key `2`, no
  stale markup.
- **Provenance** — repro A raises with the right message; scenario C does not;
  the ClassVar opt-out silences it.
- **Eager escape hatch** — the field works, and its parent is provably absent
  from both tier-2 caches.

## Corrections owed

- PR #1031's strict xfail `test_dirtying_a_nested_regions_key_reaches_that_region`
  encodes "this should eventually pass." Under this design it should **raise**.
  Rewrite as part of this work.
- The #1026 comment describes only the tag mechanism. It needs the slot mechanism
  added, and the note that `holds_spliced_components` is unreachable for reactive
  classes.
- `docs/superpowers/rebuild/runtime-decision-trees.md` and the published runtime
  artifact both state that only slots go stale. Both need the two-mechanism
  correction.

## Rejected alternatives

- **Ancestor rollup** (dirty a child's key → evict the parents that embed it).
  Correct, but reloads the shell on every interaction — the anti-island. It was
  the original consumer for a recorded edge map; the hole-time decision is a
  better one, in the opposite direction.
- **Guard without unifying** (refuse to cache slot-holding parents, add the skip
  gate for tags only). Smaller diff, but permanently forks tags and slots — which
  is where every one of these bugs came from — and makes shell components, the
  ones most worth caching, exactly the ones that cannot be.
- **Keys never flow downward** (a child's load key must come from the request,
  never a parent field). Kills 2a by construction, and forbids passing an id
  down, which is the normal way to build a page.
- **Static template scanner as a freshness mechanism.** Validated at 10/10 on
  constructed shapes and 0.7 ms over 70 real templates, but structurally blind to
  slot composition. Retained only as a possible false-positive filter for
  section 3, not as load-bearing machinery.
