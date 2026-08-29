# ADR 0003: Builtin CSS always emits before application CSS

**Status:** Accepted, 2026-08-29. Shipped in 1.9.8.

## Context

A builtin component's stylesheet (`.pjx-popover`, `.pjx-popover__trigger`,
`.pjx-button`, …) styles with a single class. The natural, documented way for
an application to restyle a builtin — `class="pjx-popover__trigger
notifications-menu__trigger"` plus a bare `.notifications-menu__trigger { }`
rule — is also a single class on the same element. Both rules land at
specificity `(0,1,0)`. When two rules tie at specificity, the CSS cascade
falls back to document order: whichever rule's `<style>`/`<link>` appears
later in `<head>` wins.

pyjinhx gave no guarantee about that order. `RenderSession.css_assets` is a
`set[Path]`, sorted alphabetically by path for byte-identical output — an
accident of filesystem layout, not a designed ordering, and it says nothing
about *origin*. Worse, CSS delivered after first paint (a builtin used for
the first time by a region that mounts later in a session) is
`document.head.appendChild`-ed, i.e. always placed *last*, regardless of
whether it's a builtin or an app rule. Whichever half of a tied pair happened
to be delivered late would jump ahead and flip the winner — not on every
render, only when a particular navigation sequence caused one half to arrive
after the other. An audit of one downstream application found 25 tied
builtin/app pairs across four routes; two had already shipped as
"the icon disappeared" / "the row got taller" bugs that looked nothing like a
cascade problem.

## Decision: partition by origin, emit builtins first, always

`pyjinhx.assets._is_builtin_asset(path)` answers the origin question with a
path check: is the path under `pyjinhx/builtins`? Builtins ship inside the
installed package; nothing else does. `emit_assets()` (the cold-render path)
and `missing_asset_oob()` (the reactive/post-paint path) both partition their
CSS paths into builtin and app groups and emit builtin CSS first, unconditionally.
Each group keeps its existing alphabetical sort internally — only the
group-level order changes, so two renders of the same tree are still
byte-identical.

For CSS delivered after first paint, sending it earlier in the same response
isn't enough on its own: `pjx.js` relocates head-targeted OOB fragments with
`appendChild`, and two different responses can arrive session-lifetime
apart. A builtin's CSS could ship in a response *this* page has already
finished processing by the time an app rule for the same element ships in a
later one. The OOB fragments for builtin CSS now carry
`data-pjx-origin="builtin"`; `pjx.js` inserts a builtin style before the
first app-owned `<style>` already resident in `<head>` instead of appending
it, and does the same when promoting a cold-rendered inline style out of the
body. Whichever order the two halves of a tied pair actually arrive in, the
builtin's rule ends up first in `<head>`.

This makes the guarantee: **a bare app selector targeting an element that
also carries a `pjx-` class always wins a specificity tie against that
builtin's rule**, in every delivery mode and at any point in a session.

## Rejected: a `@layer pjx { … }` cascade layer

The alternative on the table was wrapping every builtin stylesheet in
`@layer pjx { ... }`. An unlayered rule beats a layered one regardless of
specificity *or* document order — this would remove the ordering problem
entirely, with no client-side insertion logic needed at all, and no
"who arrived first" question to answer.

It was rejected for being a bigger, riskier change than the problem calls
for:

- **It doesn't just fix ties — it inverts every builtin/app relationship,
  at any specificity.** The bug is specifically about *tied* pairs. A layer
  change also flips pairs that are *not* tied: if a builtin's open-state
  rule is intentionally more specific than an app's base rule
  (`.pjx-popover.pjx-popover--open` at `(0,2,0)` vs. the app's `.foo` at
  `(0,1,0)`), today the builtin correctly wins on specificity. Wrapping
  builtins in a layer would make the *unspecific* app rule win instead,
  silently breaking any builtin behavior that currently depends on winning a
  higher-specificity contest — a much larger and harder-to-audit blast
  radius than "ties resolve deterministically now."
- **The origin split this ADR needs already exists and is cheap** (a path
  check under `pyjinhx/builtins`), so the ordering fix costs little; `@layer`
  would have needed the same split just to know what to wrap, for a bigger
  behavior change on top.
- **Browser support is not the deciding factor** — `@layer` has been broadly
  supported since early 2022 — but a change with no sharp edge on the
  surface (2 above) is preferable to one that removes an entire bug class at
  the cost of an unaudited, silent behavior inversion.

`@layer` remains available to reconsider if a future audit shows builtins
relying on specificity wins is rare enough, or if pyjinhx wants a stronger
guarantee (app always wins, tied or not) as a deliberate, documented
behavior change rather than a side effect.

## Consequences

- **Only ties are affected.** A builtin rule that already wins on higher
  specificity keeps winning; this ADR does not touch specificity, only the
  tie-break that document order used to decide unpredictably.
- **Existing "qualify the selector" workarounds
  (`.pjx-popover__trigger.my-trigger { }`) still work** — they were already
  more specific than the builtin, and this ADR doesn't change their standing.
- **`all_assets()` (used for one-bundle deployment, `docs/guide/assets.md`)
  is unchanged** — it still returns a flat, alphabetically sorted tuple
  across every registered component regardless of origin. An app building its
  own bundle from `all_assets()` must apply the same builtin-first split
  itself if it wants the guarantee to hold in that bundle too.
- **JS ordering is untouched.** The tie-break problem is specific to CSS
  cascade order; nothing about accumulated JS emission order changed.

## Related

- [Asset Collection](../guide/assets.md#css-ordering-guarantee) — the
  app-facing statement of the guarantee.
- Issue #1058 — the worked example, the 25-pair audit, and the original
  three-option proposal this ADR resolves.
