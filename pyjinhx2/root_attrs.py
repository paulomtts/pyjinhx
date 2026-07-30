"""Root-attr stamp: splice a component's pass-through attrs into its
RenderedLevel's root opening tag, at the already-recorded root_span.

Import-pure (stdlib only) — this module may not import pyjinhx2.render,
pyjinhx2.component, or pyjinhx2.session (same rule as pyjinhx2.segments).
Single-root detection is NOT this module's job: it trusts the root_span
it is given, produced by an earlier L0 step (issue #247's detection pass
via VerbatimParser in pyjinhx2/segments.py). This module never re-parses;
it only slices and concatenates strings.

Port of v1 pyjinhx/root_attrs.py's `apply_root_attrs` / `_override_tag`
behavior, scoped to L0: only pass-through attrs land here. `data-pjx-*` /
`hx-swap-oob` stamping (L2/L3) reuses this same splice at the same span.
"""

import re

from pyjinhx2.segments import RenderedLevel


def serialize_attr(name: str, value: str) -> str:
    """Emit ``name="value"``; fall back to single quotes when the value has ``"``."""
    if '"' in value:
        if "'" in value:
            raise ValueError(
                f"attribute {name!r} value must not contain both '\"' and \"'\""
            )
        return f"{name}='{value}'"
    return f'{name}="{value}"'
