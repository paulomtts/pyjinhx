# ADR 0006: Strict Pydantic core, open opt-in subclass

**Status:** Accepted, 2026-07-28.

## Context

v0.x sets `extra="allow"` on `BaseComponent`. It buys stray-attribute pass-through (#75) and classless-component ergonomics (`{#def#}` headers, `component()`), but forces a per-render walk over undeclared keys in `_build_template_context` — hot-path work paid by every component whether or not it uses the feature, and the direct cause of the #240 Task 6 crash (`dictionary changed size during iteration`). The rebuild analysis rated this "no clean answer": strict is faster and safer; open is what two shipped features stand on.

## Options

1. **Open everywhere** — today's model; per-render cost for all.
2. **Strict everywhere** — fastest; kills stray-attr pass-through and weakens classless components.
3. **Strict core, open opt-in subclass** — `BaseComponent` strict; a designated open-model base (or `model_config` override) for classless/`{#def#}` components.

## Decision

Option 3. The cost follows the feature: components that need extra-field acceptance opt into it; everything else renders with zero undeclared-key work. Both ergonomic features survive unchanged on the open subclass — `{#def#}`-headed templates and `component()` build on it.

## Consequences

- Strict components skip the undeclared-key walk entirely.
- Stray-attribute pass-through works only on open-model components; class-based components wanting pass-through declare the subclass. Migration note required (PRD G5).
- Two base classes to document; the descriptor (overview invariant 5) records which mode a class uses, so the renderer branches once per class, not per render.
