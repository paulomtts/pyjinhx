# ADR 0001: outerHTML-only OOB swaps, no append/prepend modes

**Status:** Reconstructed. This ADR was not written when the reactive engine
was designed — it was assembled after the fact from a conversation that
walked through the mechanism and probed why append-mode OOB swaps don't
exist. Treat the *mechanism* description as verified against source; treat
the *original intent* framing as inferred, not confirmed by whoever wrote
the original engine.

## Context

pyjinhx's reactive engine re-renders and swaps components over htmx OOB
(out-of-band) swaps. On every htmx request, the client scans the DOM for
mounted reactive components and sends a manifest of `{id, type, load, hash}`
(the `X-PJX-Mounted` header, read by `pyjinhx/client/inject.py`). The server
uses that manifest plus a set of "dirtied" keys to decide which mounted
instances need a fresh render.

For a dirty candidate, `oob_swaps()` emits `outerHTML:[data-pjx-id='...']`
(`pyjinhx/reactive/fanout.py`, in `oob_swaps()`) — a full-replacement swap
targeted at a specific mounted component's root element. There is no append,
prepend, or `beforeend`-style OOB swap mode. (A separate `delete:` swap mode
also leaves this function, for a different case — see below.)

The question that prompted this ADR: given hash-gating lives on the parent's
own tag (`state_hash()`, `pyjinhx/reactive/component.py`, computed via
`model_dump()` minus `state_hash_exclude` — `id` is excluded by default,
`pyjinhx/reactive/component.py`), appending a child *would* change the
parent's hash and *would* be detected. So why doesn't append-mode OOB exist?

## Decision

Support exactly one *update* swap mode (`outerHTML`) and push
delta-granularity onto component composition instead of swap-mode variety.
(`oob_swaps()` also emits a second, structurally different `delete:` swap for
regions the client still shows but the registry no longer knows about — see
"Consequences" — but that's a removal signal, not an update-shape choice, and
doesn't reopen the append/prepend question this ADR is about.)

Two things make append-mode redundant rather than missing:

1. **Rendering is always full-current-state, never a delta.** `.load()` +
   render always produces the complete current HTML for a component's
   subtree; there's no code path that renders "only the new item." Hashing
   on the parent can *detect* that something changed (including an append),
   but detection isn't the same as being able to *emit* just the appended
   fragment — the render pipeline has no notion of a diff to emit.
2. **Fine-grained delta control already exists via nesting.** Any
   `ReactiveComponent`, at any nesting depth, gets its own `data-pjx-id` /
   `data-pjx-hash` stamped independently. On a normal render this is
   `stamp_reactive_root_attrs()` (`pyjinhx/reactive/root_attrs.py`), an
   `on_rendered` subscriber; on the dirty/OOB path that stamper isn't wired
   onto the session `oob_swaps()` uses, so `oob_swaps()` stamps
   `data-pjx-hash` itself from the freshly computed hash instead
   (`pyjinhx/reactive/fanout.py`). Either way, each nested instance is
   independently reactive and independently participates in `oob_swaps()`'s
   manifest-driven matching loop. So a developer who wants
   per-row/per-item granularity gets it today by mounting a keyed child
   component per row (`react={...}` + a load-key) — issue #201's
   `reactive_key()` sharpened this further by letting a *single* mutation
   target one derived key instead of the whole shared key, without adding a
   new swap mode.

Introducing genuinely new content (an item that didn't exist in any previous
manifest) is a **primary swap** concern, not an OOB concern: it's ordinary
htmx (`hx-swap="beforeend"` or similar) delivering markup that, once
mounted, contains its own `data-pjx-id`/`data-pjx-hash` and is fully
OOB-reactive from the *next* request onward. Primary swap introduces;
OOB tail updates already-mounted siblings. These are complementary
mechanisms, not competing ones — and once combined with nesting, they cover
what an append-mode OOB swap would have covered, without a second swap
format to hash-compare, validate, and keep in sync with `oob_swaps()`'s
pre-filter/matching logic.

## Consequences

- **No new *update*-swap-mode surface area.** For content that changed,
  `oob_swaps()` only ever needs to reason about one shape of comparison
  (full-subtree hash vs. full-subtree re-render), which keeps hash-gating
  simple: one hash per mounted instance, one comparison, one swap format.
  A second, structurally distinct swap does exist — `delete:` — but it isn't
  an update mode: `delete_swap()` emits
  `<div hx-swap-oob="delete:[data-pjx-id='ID']"></div>` for a "missing"
  candidate (an instance the client's manifest still reports but the
  registry no longer knows about), removing the stale region instead of
  re-rendering it. `oob_swaps()`'s own docstring ties this to ADR 0001: only
  `outerHTML:` and `delete:` ever leave that function. It doesn't reopen the
  append/prepend question above — there is still no delta/fragment swap for
  *content that changed*, only a full-replace-or-remove choice for content
  whose presence changed.
- **The cost is developer discipline, not framework capability.** Getting
  fine-grained updates requires deliberately breaking a UI into
  keyed/nested components at the granularity you want to update
  independently. A monolithic list rendered as one big component will
  always re-render as one big `outerHTML` swap on any dirty key it reacts
  to — `reactive_key()` (issue #201) narrows *which* keys trigger that, not
  *how much* HTML moves when it does.
- **New content must go through a primary swap**, not `dirty()` /
  `ReactiveResponse()` alone — those only affect components already present
  in the client's mounted manifest. This is occasionally surprising: dirtying
  a key does nothing for content that isn't mounted yet.

## Alternatives considered

- **Append/prepend OOB swap modes.** Rejected implicitly by never being
  built — would require the render pipeline to produce a delta fragment
  (not just full current state) and would double the swap-format surface
  `oob_swaps()` has to support, for a case nesting already covers.
- **Diffing/patching swaps** (morphdom-style). Same shape of rejection: adds
  a second rendering mode and a diff engine, for marginal gain over
  full-subtree `outerHTML` once components are nested at the granularity
  that actually needs independent updates.

## Related

- [`reactive_key()` / parametric reactive keys](../reactivity.md) — issue
  #201, sharpens key-level granularity within the existing outerHTML model.
