"""Root-attr stamp: splice a component's pass-through attrs into its
RenderedLevel's root opening tag, at the already-recorded root_span.

Import-pure (stdlib only) — this module may not import pyjinhx.rendering,
pyjinhx._component, or pyjinhx.session (same rule as pyjinhx.segments).
Single-root detection is NOT this module's job: it trusts the root_span
it is given, produced by an earlier L0 step (issue #247's detection pass
via VerbatimParser in pyjinhx/segments.py). This module never re-parses;
it only slices and concatenates strings.

Port of v1 pyjinhx/root_attrs.py's `apply_root_attrs` / `_override_tag`
behavior, scoped to L0: only pass-through attrs land here. `data-pjx-*` /
`hx-swap-oob` stamping (L2/L3) reuses this same splice at the same span.
"""

import re

from pyjinhx.segments import RenderedLevel


def serialize_attr(name: str, value: str) -> str:
    """Emit ``name="value"``; fall back to single quotes when the value has ``"``."""
    if '"' in value:
        if "'" in value:
            raise ValueError(
                f"attribute {name!r} value must not contain both '\"' and \"'\""
            )
        return f"{name}='{value}'"
    return f'{name}="{value}"'


def _override_tag(tag_text: str, attrs: dict[str, str]) -> str:
    """Apply ``attrs`` onto a single opening-tag string with override semantics."""
    body = tag_text
    for name, value in attrs.items():
        pair = serialize_attr(name, value)
        pattern = re.compile(
            r"\s" + re.escape(name) + r"\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s/>]*)"
        )
        if pattern.search(body):
            body = pattern.sub(" " + pair, body, count=1)
        elif body.rstrip().endswith("/>"):
            idx = body.rindex("/>")
            # rstrip intentional: prevents extra space before '/>'
            # (e.g. '<br data-y="1"/>' not '<br  data-y="1"/>')
            body = body[:idx].rstrip() + " " + pair + body[idx:]
        else:
            idx = body.rindex(">")
            body = body[:idx] + " " + pair + body[idx:]
    return body


def stamp_root_attrs(level: RenderedLevel, attrs: dict[str, str]) -> RenderedLevel:
    """Splice ``attrs`` into ``level``'s root opening tag at ``level.root_span``.

    No-op (identity) when ``attrs`` is empty. Otherwise replaces the
    ``root_span`` substring of ``level.segments[0]`` with the stamped tag
    text and updates ``root_span`` to match the new tag's length. Mutates
    ``level`` in place and returns it, matching the ``splice()`` convention
    in ``pyjinhx.segments``.

    When a component's whole template is one child tag, the renderer has
    already replaced ``segments[0]`` with that child's own RenderedLevel by
    the time this runs, so the root tag to stamp lives one level down: the
    call recurses into it and the outer ``level.root_span`` is left alone,
    since in that shape it bounds nothing this module owns and nothing reads
    it. The returned object is still the outer ``level``, so the
    mutate-and-return contract holds at every depth.
    """
    if not attrs:
        return level
    root = level.segments[0]
    if isinstance(root, RenderedLevel):
        stamp_root_attrs(root, attrs)
        return level
    assert isinstance(root, str), (
        "stamp_root_attrs needs a str or RenderedLevel root segment, "
        f"got {type(root).__name__}"
    )
    start, end = level.root_span
    new_tag = _override_tag(root[start:end], attrs)
    level.segments[0] = root[:start] + new_tag + root[end:]
    level.root_span = (start, start + len(new_tag))
    return level
