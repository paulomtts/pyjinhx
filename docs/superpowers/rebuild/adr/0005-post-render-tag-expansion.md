# ADR 0005: Post-render tag expansion, one parse per level

**Status:** Accepted, 2026-07-28.

## Context

PascalCase tags (`<PJXButton .../>`) must become component renders. v0.36 finds them by feeding rendered output through `html.parser` — validated by the #240 spec as sound: only PascalCase tags are special-cased, everything else passes through verbatim via `get_starttag_text()`, preserving unknown attributes, quoting, and intentional malformed HTML. The alternative — a compile-time Jinja extension turning static tags into call nodes — was rated "big prize, big risk" by the rebuild analysis: the prize was mostly deleting the opacify apparatus, and it fails for *generated* tags (loops emitting `<PJXTableCell>` from data, slot values containing literal tag text), so both paths would be needed.

## Options

1. **Post-render parse per level** — `html.parser` over the level's own output only (ADR 0002 guarantees children are never re-parsed).
2. **Compile-time extension + runtime fallback** — static tags become call nodes; runtime parse only when output still contains PascalCase. Two expansion paths to keep semantically identical.
3. **Compile-time only** — generated tags unsupported; loops must call `component()` explicitly. Breaks a real, documented pattern.

## Decision

Option 1. ADR 0002 already claims the compile-time prize (opacify is dead regardless), collapsing the tradeoff: what remains of option 2 is a second expansion path bought for a per-level parse that the #240 spec already ruled inherent. Generated tags work naturally; the `contains_custom_tag` regex prepass carries over to skip parsing leaf output.

## Consequences

- One `html.parser` feed per level, doing double duty (ADR 0002): child-tag cut points and root-span recording in the same pass. Total parse cost O(S) per page.
- Generated tags and static tags expand through the identical path — no semantic-parity burden.
- Verbatim pass-through of all non-PascalCase markup is preserved, same as v0.x.
