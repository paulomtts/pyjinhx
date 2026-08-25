# Design: nested reactive freshness — a cache entry never contains another component

**Date:** 2026-08-25
**Status:** Approved, pending implementation plan
**Issues:** #1022, #1026, #1027, #1028
**Breaking:** yes — lands additively in a 1.x minor, enforced in 2.0

## The rule

> **A cache entry never contains another component.**
> A component-typed field holds a *reference*, never a loaded component.

The render cache already obeys this. `_finish_cached_level` restores a level's
own segments and leaves its child holes as `ChildRef`s, so a hit rebuilds
children live. Measured on a cacheable `Shell` containing `<Leaf/>`, rendered
three times:

```
render #1  templates built: ['Shell', 'Leaf']
render #2  templates built: ['Leaf']      <- Shell restored, Leaf rebuilt
render #3  templates built: ['Leaf']
```

The load cache does not obey it. A slot-composing parent's cached `load()` result
holds the loaded child instance — the child's *data*, cached one level too high.

That asymmetry is the whole problem. Everything below follows from making the
load cache obey the same rule the render cache always has.

## Problem

Three defects share one cause: the runtime knows each parent→child edge at the
moment it fills a child hole, and never acts on it there.

### 1. Clean children still load

Island reactivity promises two savings. Fan-out delivers one: a region whose
declared keys were not dirtied never reaches the wire. The other is not built —
every clean component still runs `load()`, renders its template, and has the
markup discarded by fan-out.

The reason is structural. `get_dirtied()` is read in exactly one production path
(`responses.py:61`, inside `_fan_out`), which runs *after* the primary render. By
the time anything asks what was dirtied, every `load()` has already executed.
Neither `rendering.py` nor `_wrap_load` reads it at all.

Measured on a five-level reactive chain, each level declaring its own key:

```
cold render                              loads: L0 L1 L2 L3 L4   (5)
L0 fully cached, descendants evicted     loads:    L1 L2 L3 L4   (4)
only 'key0' dirtied                      loads: L0               (1, all 5 asked)
no tier-2 backend, request 2, nothing dirtied
                                         loads: L0 L1 L2 L3 L4   (5)
```

Output is always correct. This is a missing optimization — but it is the one the
library's design intent was written around.

### 2a. Tag composition serves a stale load key

A child whose key flows through its parent's data inherits that parent's
staleness:

```
dirtied 'conversation'; user moved from conversation 1 -> 2

A  baseline (parent reacts to 'view' only)   child.load called: ['1']  stale: True
B  child given cache=False                   child.load called: ['1']  stale: True
C  parent reacts to ('view','conversation')  child.load called: ['2']  stale: False
```

The child's entry *is* evicted and its body *does* run — against a key read off a
parent that was not evicted. Opting the child out of caching does not rescue it;
only widening the parent's react set does.

What scenario C buys is **fresh props**, not a reload. The child reloads either
way — that is defect 1. The rule it implies: *a parent depends on every key whose
value it passes down as an identity.* Not all its children's keys — a child
reacting to `("conversation", "unread")` whose parent only feeds `conversation`
leaves `unread` to the child's own eviction.

### 2b. Slot composition freezes the child entirely

When a parent builds its child in Python, the child is a fully-loaded instance
inside the parent's cached `load()` result. There is no hole, so no decision
point:

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
(`rendering.py:336`), so the slot gate three lines down is never evaluated for the
components that have this bug. The freeze is in the **load** cache.

ADR 0003 makes every component-typed field a slot structurally, so this surface is
every nested component built in Python — not an opt-in few.

## Decision

Make `_fill_children` the single freshness decision point, for tags and slots
alike, at the moment the hole is filled and before the child loads.

```
_fill_children reaches a child hole
   |- resolve class -> declared react keys
   |- bind props    -> load key value
   |- dirtied this request?  -- no --+- client holds THIS child? -- yes -> PRESERVE
   |                                 \- no -----------------------------> load
   \- yes -> parent served from cache?
               |- no  -> load (fresh props)
               \- yes -> raise (provenance error)
```

Two facts make this feasible without new plumbing:

- `session.pjx_mounted` is populated by middleware *before* the handler runs
  (`integrations/fastapi.py:213`, inside `request_scope`, before `call_next`), so a
  hole-time decision can already ask what the client holds.
- `_load_reactive_child` (`rendering.py:111`) already resolves the class, pulls the
  key attr out of the props, and coerces it to the field's declared type — all
  before `cls.load(**key_args)`. That line is the decision point.

No template scanner, no recorded edge map, no ancestor rollup. The parent→child
edge is consumed at the instant it exists and never stored.

## Section 1 — References

`ReactiveComponent` gains one classmethod:

```python
class Shell(ReactiveComponent, react=("view",)):
    content: Child | None = None

    @classmethod
    def load(cls, view: str) -> "Shell":
        return cls(id="shell", content=Child.ref(conversation=view))
```

`Child.ref(**props)` returns a frozen `(class, props)` pair. It runs no `load()`,
touches no cache, holds no data — the Python spelling of what
`<Child conversation="…"/>` already produces as a `ChildRef` (`segments.py:12`).
Component-typed fields are detected structurally at registration (ADR 0003), which
is where acceptance of a `Ref` goes.

What ends up in the parent's cached value is the whole point:

```python
# eager — caches the child's DATA one level too high. This is 2b.
Shell(content=Child(conversation="1", body="messages-of-1"))

# ref — caches an INSTRUCTION. Re-decided every request.
Shell(content=Ref(Child, {"conversation": "1"}))
```

### No eager escape hatch

Assigning a **loaded** reactive component to a component-typed field raises. There
is no opt-out annotation.

A parent that needs a child's data depends on that data, and should declare and
fetch it as its own concern. Sanctioning an eager field would sanction exactly the
undeclared dependency section 3 raises about.

Loading *inside* `load()` is still fine — what is forbidden is storing the result
in a field:

```python
@classmethod
def load(cls, view: str) -> "Shell":
    ids = fetch_ids(view)
    ids.sort(key=lambda i: Invoice.load(invoice=i).total)      # read it
    return cls(content=[Invoice.ref(invoice=i) for i in ids])  # store refs
```

Tier 1 dedups within the request, so each child hits cache at its hole rather than
re-fetching. No double query.

### Bare construction

A bare `Child(...)` is already an unloaded instance — `load()` is a separate
classmethod — so it is accepted at the hole on the same terms as a `Ref`. It is not
documented as the way, because it fails on any class with a required load-supplied
field:

```
Messages  bare construct OK   -> Messages(conversation='1', body='', unread=0)
Invoice   bare construct FAILS -> ValidationError: total  Field required
```

That failure's obvious workaround is `Invoice.load(...)`, which is exactly what
now raises. `ref()` records props rather than building a model, so it works for
both classes identically.

### What a parent may still read

`.props` keeps working, because props are precisely what a reference holds. Only
load-supplied fields become unreachable — the intended discipline, and the same
argument ADR 0003 already makes about a child's markup, applied one layer down to
a child's data.

### Collections

`list[Child]` and `dict[str, Child]` are already slots (`_holds_component` checks
both). The container is a plain Python object — only its elements are opaque — so
iteration was never restricted:

```python
content=[Messages.ref(conversation=c) for c in ids]
```

```jinja
{% for c in content %}{{ c }}{% endfor %}
```

Each `{{ c }}` becomes its own hole with its own freshness decision: a 50-row list
where one row changed loads 1 and preserves 49.

Two consequences:

- `build_context` must wrap a `Ref` the way it wraps a component, so `{{ c }}`
  emits a slot token.
- Preservation needs a stable authored id **per element** (section 2, condition 4).
  Rows normally have one from their data (`<li id="row-{{ conversation }}">`). With
  auto `pjx-N` ids the gate fails and every element simply loads — correct, no
  savings. This is the single thing to get right for lists, and belongs in the docs
  as such.

## Section 2 — The decision at the hole

### Constraint

`hx-preserve` is resolved by htmx through the incoming tag's plain `id`
(`getElementById`), not `data-pjx-id` (`fanout.py:825`). Preservation therefore only
lands for a region whose template root carries a stable authored id. And
`hx-preserve` is a no-op for an id the client does not already show — which for a
placeholder means shipping an empty element. **The manifest check is mandatory, not
an optimization.**

### The skip gate

Skip a child only on positive proof of all five conditions:

| # | condition | existing machinery |
|---|---|---|
| 1 | reactive class | `_pjx_key_field` |
| 2 | no declared key dirtied this request | `_keys_match_dirtied` |
| 3 | manifest holds this id, type, **and load key** | `session.pjx_mounted` |
| 4 | root id is authored, not auto | `has_auto_id` |
| 5 | class opts in | `retain_across_parent_swaps` (default `True`) |

Four of five already exist. `retain_across_parent_swaps` is already the per-class
switch for this question in the OOB path; reusing it means one flag governs
preservation everywhere. Its default of `True` means existing components get
islands without opting in.

Any failed condition falls back to loading and rendering, exactly as today — the
same conservative posture `_preserve_nested` takes: skip only on proof.

### Condition 3 does two jobs

It answers "does the client have this region" **and** "is it still the same child."
The second is load-bearing for correctness, not just for savings:

```
'view' dirtied, 'conversation' NOT dirtied
  Shell reloads (declares 'view')  ->  now passes conversation="2"
  Child's own keys clean           ->  would preserve...
  ...but the mounted region's load key is "1" and the child now resolves to "2"
  -> condition 3 fails -> the child loads
```

Without the load-key half of the match, a fresh parent naming a different child
would serve the old one. The full rule a child loads under:

```
child loads  <=>  its keys were dirtied
              or  the parent now names a different one
              or  the client does not have it
```

### What gets emitted

```html
<div id="messages" hx-preserve="true"></div>
```

One new requirement: manifest entries gain the region's **root tag name**, so the
placeholder matches the live element. `pjx.js` has it at mount time; an added
field, not a new mechanism.

### Consequences

- **Descendants are independent.** `walk_manifest` reads the client's manifest, not
  what was rendered, so a dirty grandchild under a skipped parent still gets its own
  OOB leg — and `_drop_nested` will not swallow it, because the skipped parent's
  placeholder does not contain it.
- **Cold loads are correct by construction.** Empty manifest → condition 3 fails
  everywhere → the whole tree loads. No special case.
- **Slots join here.** `_splice_slot_nodes` hands a `Ref` to the same gate a
  `ChildRef` goes through.

## Section 3 — Provenance and the 2a error

### The stamp

`_wrap_load` already branches on `cache_has(...)`. Mark instances returned from
either tier with `_pjx_from_cache = True`. One assignment, one place — the only new
state in this design.

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

The repair — evict the parent, re-run its `load()` — is always correct and needs no
analysis, but it fires on every interaction in the exact shape this library is built
for (shell plus keyed region). The shell would reload every request: the cascade
section 2 exists to kill, reintroduced through the back door. Raising costs nothing
at runtime and states the true fact — the parent depends on that key. Repro scenario
C is that fix, and it already works today.

### Accepted false positive

A literal key (`<Leaf leaf="x"/>`) under a cached parent whose `leaf` was dirtied has
no data flow, and this rule raises anyway. Two filters were considered and rejected as
premature: a template scan (precise for tags, structurally blind to refs) and a
value-membership test against the parent's fields (covers both, misses computed keys).
Both are two mechanisms where one would do, for a case that hardcodes an identity into
markup. Ship the coarse rule and the ClassVar opt-out; add a filter only if real code
trips it.

### Blast radius

The check can only fire when a parent came from cache, which requires a tier-2
backend. The default configuration has none, so no default-configured app can hit
this — and the apps that can are exactly those silently serving stale data today.

Refs get this for free: a `Ref` built inside a cached parent's `load()` carries the
same staleness as an interpolated tag attr, and the same stamp on the same parent
catches it. One rule, both composition forms.

## Section 4 — Migration

Five changes, in descending blast radius:

1. **A loaded reactive component in a component-typed field raises.** Mechanical
   migration: `Child.load(x)` → `Child.ref(x)`. Where the parent needs the child's
   data, it declares and fetches that data as its own field — or reads it inside
   `load()` without storing the instance.
2. **A parent can no longer read a child's load-supplied fields.** `.props` still
   works; anything `load()` filled does not. Parents that relied on it declare the
   value themselves.
3. **The 2a provenance raise.** Unreachable without a tier-2 backend.
4. **Clean children stop running `load()`.** The real semantic break: any `load()`
   with side effects — a hit counter, a lazy write, an audit log — silently loses
   them. Needs a prominent migration note. `load()` is a read, and the runtime now
   holds authors to it.
5. **Manifest gains a root tag name.** An old client sending the old manifest fails
   condition 3, so those children load exactly as today. Graceful degradation, no
   version negotiation.

**Release order:** ship `ref()` additively in a 1.x minor with no enforcement so
authors can migrate at their own pace; flip the raises and the skip gate on in 2.0.
One extra release turns a cliff into a ramp.

## Implementation phases

**Phase 1 — additive, 1.x minor. No behavior change.**

1. `Ref` type and `ReactiveComponent.ref()`.
2. Component-typed fields accept a `Ref`; `build_context` wraps one so `{{ c }}`
   emits a slot token; `_splice_slot_nodes` resolves it through the same path a
   `ChildRef` takes.
3. `_pjx_from_cache` stamp in `_wrap_load`.
4. Manifest gains the root tag name; `pjx.js` emits it.

At the end of phase 1 every new spelling works, nothing raises, and no child is
skipped. 2b's staleness is already fixed for anyone who has migrated, because a
`Ref` cannot freeze.

**Phase 2 — enforcing, 2.0.**

5. The skip gate in `_fill_children`, all five conditions, plus the preserved
   placeholder.
6. The provenance raise and its `trust_cached_props` opt-out.
7. The raise on assigning a loaded reactive component to a component-typed field.
8. Migration note for side-effecting `load()` bodies.

Phase 2 is where the invariant test flips from 4 descendant loads to 0.

## Section 5 — Testing

The existing scratchpad repros are the corpus: `repro_1026_full.py`,
`blindspot_slot.py`, `invariants.py`, `what_is_cached.py`, `autostrip.py`.

**The invariant test, first and loudest.** The five-level chain, asserting the
original design intent: *no `load()` body runs for a child whose keys were clean and
whose region the client holds.* Currently 4 descendant loads; should become 0. The
one test that fails today for the right reason.

Per mechanism:

- **Skip gate** — five tests, one per condition, each proving a failed condition
  falls back to loading. Conservative-by-default is tested as the default.
- **Identity change** — parent dirty, child clean, child's load key changed: the
  child must load. Guards condition 3's second job.
- **Preserve output** — placeholder carries the authored id, `hx-preserve="true"`,
  and the manifest's root tag.
- **Cold load** — empty manifest, whole tree loads.
- **Descendant independence** — dirty grandchild under a skipped parent gets its own
  OOB leg and is not swallowed by `_drop_nested`.
- **Slot refs** — `blindspot_slot.py` inverted: child loads with key `2`, no stale
  markup.
- **Collections** — `{% for c in content %}` over a list of refs: one dirty element
  loads, the rest preserve; and with auto ids, all load.
- **Provenance** — repro A raises with the right message; scenario C does not; the
  ClassVar opt-out silences it.
- **No eager** — assigning a loaded reactive component to a component-typed field
  raises; loading inside `load()` without storing it does not.

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

- **An eager escape hatch** (`Annotated[Child | None, Eager()]`, with eager parents
  made uncacheable). Sanctions the same undeclared dependency section 3 raises about,
  and costs a second rule for a case the sort-then-ref pattern already covers.
- **Automatic strip on cache write** — replace any loaded child in a field with a
  `Ref` at write time, requiring no new API and no migration. Fails because the load
  key is recoverable but the parent's own props are not. Given
  `Messages(conversation='1', body='msgs-1', variant='compact')`, where `body` came
  from `load()` and `variant` from the parent, nothing on the instance distinguishes
  them: store the key alone and `variant` is silently dropped; store every field and
  the child's data is back in the parent's entry, which is 2b. Explicit `ref()`
  resolves the ambiguity by having the only party who knows state the props — the same
  convention `_load_reactive_child` already applies to tag attrs.
- **Ancestor rollup** (dirty a child's key → evict the parents that embed it).
  Correct, but reloads the shell on every interaction — the anti-island.
- **Guard without unifying** (refuse to cache slot-holding parents, skip gate for tags
  only). Permanently forks tags and slots, and makes shell components — the ones most
  worth caching — exactly the ones that cannot be.
- **Keys never flow downward.** Kills 2a by construction, and forbids passing an id
  down, which is the normal way to build a page.
- **Static template scanner as a freshness mechanism.** Validated at 10/10 on
  constructed shapes and 0.7 ms over 70 real templates, but structurally blind to slot
  composition. Retained only as a possible false-positive filter for section 3.
