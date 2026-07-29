# ADR 0003: Slots are opaque — truthiness and interpolation only

**Status:** Accepted, 2026-07-28. Consequence of ADR 0002.

## Context

Under v0.36's string model, a slot value is a genuine string during `template.render()`, so `{{ content|length }}`, `content in x`, and `{{ content|striptags }}` all work — this is precisely why v0.36 opacifies the *output* rather than the *context*, at real complexity cost. Under ADR 0002, child output is an opaque node; a slot holding a component cannot be a plain string without re-flattening structure.

## Options

1. **Opaque + truthiness only.** Templates may test `{% if content %}` and interpolate `{{ content }}`. String filters on component slots raise with a clear error naming the slot and the fix.
2. **Lazy stringify.** Opaque node implements `__str__`/`__len__`, forcing early child render when inspected. Filters keep working; hidden eager rendering reintroduces string-model complexity into layer 0 and makes render order data-dependent.
3. **Survey-then-decide.** Defer until slot-filter usage in builtins/docs is measured.

## Decision

Option 1, with option 3's survey folded in as a pre-RFC-1 gate (PRD risk 1): grep builtins and docs for string operations on slot values before layer 1's RFC. If usage turns out widespread, this ADR gets revisited *before* L1 — not discovered after.

String-valued slots (a `Slot` field assigned a plain string) are unaffected — they remain raw-HTML-capable strings. This ADR governs slots holding rendered components.

## Consequences

- Child opacity stays absolute; no hidden render forcing; layer 0 stays simple.
- `{% if content %}`, `{{ content }}` work; `{{ content|length }}` on a component slot raises a targeted error instead of silently misbehaving.
- Migration note required for any v0.x template using string filters over component slots (expected rare; verified by the survey).
