# ADR 0010: MRO template/asset resolution kept

**Status:** Accepted, 2026-07-29.

## Context

v0.x resolves a component class with no template of its own by walking its MRO (Python inheritance chain) and using the nearest ancestor's template; template, CSS, and JS resolve independently per kind. This is what makes extending a builtin a three-line class:

```python
class DangerButton(PJXButton):  # no danger_button.pjx anywhere
    variant: str = "danger"  # inherits pjx_button.pjx + its JS,
    # may ship only danger_button.css
```

Without it, every subclass duplicates the parent's template file, which then drifts when the parent's template changes. The cost in v0.x was extra probes through the six-candidate matrix; under ADR 0007 the matrix is 1×1.

## Options

1. **Drop** — subclasses copy templates; simplest finder, drift risk on every extension.
2. **Keep** — walk MRO at registration, one candidate per ancestor per kind, result frozen into the descriptor.

## Decision

Option 2. The feature is the mechanism behind "extend a builtin without forking its markup," its consumers are real (L4 builtins are designed for subclassing), and under ADR 0007 + the descriptor (overview invariant 5) its entire cost is a handful of filesystem probes paid once at class registration. Zero render-time cost.

## Consequences

- Per-kind independence preserved: a subclass may override CSS while inheriting template and JS.
- Resolution happens in `__pydantic_init_subclass__` into the frozen descriptor; dev-reload invalidation goes through the descriptor's single invalidation point like everything else.
- The descriptor records *which ancestor* supplied each kind — free provenance for error messages and the dependency graph.
