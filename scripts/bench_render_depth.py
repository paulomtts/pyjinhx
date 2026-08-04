"""Render-scaling benchmark for the pyjinhx kernel: depth held apart from breadth.

bench_render_scaling_v2.py sweeps component *count* through a tree that is
always exactly 3 levels deep; nothing there isolates depth from breadth, so a
render whose cost scales with nesting depth (rather than sibling count) would
not show up in it. This script holds breadth at 1 (a single linear chain, no
siblings) and sweeps depth instead, so any depth-driven cost — the cycle-guard
chain check in render_level(), context/scope propagation through nested
renders, recursive fill/serialize — is visible on its own.

Each level is a distinct dynamically-built class: render_level()'s cycle guard
raises on a class name re-appearing in the current call chain (ADR 0004), so a
single self-nesting class could not reach any real depth, and reusing a small
rotation of classes would let the cycle guard's own chain-membership check
(a `name in chain` scan of the *whole* chain so far) confound the reading —
distinct classes keep that check at its cheapest (always a miss) and isolate
pure depth cost.

Not a CI test (timing-sensitive). Run manually before/after render-path work:

    uv run python scripts/bench_render_depth.py
"""

import tempfile
import time
from pathlib import Path

from pyjinhx import discovery
from pyjinhx._component import BaseComponent, _pascal_to_snake
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

DEPTHS = (10, 20, 40, 80, 160)


def _descriptor(cls: type[BaseComponent], template: str) -> ClassDescriptor:
    """Minimal descriptor pointing at a temp-dir template, no children field."""
    return ClassDescriptor(
        template_path=Path(template),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


def build_chain(depth: int, template_dir: Path) -> type[BaseComponent]:
    """Build ``depth`` distinct classes, each nesting the next, and return the root.

    Level i's template embeds a ``<BenchDepthLevelI+1/>`` tag; the last level's
    template is a leaf with no child tag. Each class and its template are named
    uniquely per depth-run so successive calls at different depths never share
    (and therefore never register over) an earlier run's classes.
    """
    classes: list[type[BaseComponent]] = []
    for i in range(depth):
        # No underscores: RE_PASCAL_CASE_TAG_NAME (pyjinhx/segments.py) only
        # matches [A-Za-z0-9]* after the leading capital, so an underscore
        # would make the parser treat the tag as literal text, not a ChildRef.
        class_name = f"BenchDepthLevel{depth}Idx{i}"
        cls = type(
            class_name,
            (BaseComponent,),
            {"label": "level", "__annotations__": {"label": str}},
        )
        classes.append(cls)
        is_leaf = i == depth - 1
        source = f'<div class="level-{i}">{{{{ label }}}}'
        if not is_leaf:
            child_name = f"BenchDepthLevel{depth}Idx{i + 1}"
            source += f'<{child_name} label="{{{{ label }}}}"/>'
        source += "</div>"
        template_name = f"{_pascal_to_snake(class_name)}.pjx"
        (template_dir / template_name).write_text(source)
        cls.__pjx_descriptor__ = _descriptor(cls, template_name)
        discovery._registry.mapping[_pascal_to_snake(class_name)] = cls
    return classes[0]


def bench_depth(depth: int) -> float:
    """Build and render one depth-``depth`` linear chain once; return elapsed seconds."""
    template_dir = Path(tempfile.mkdtemp())
    discovery._registry.mapping = {}
    root_cls = build_chain(depth, template_dir)
    session = RenderSession()
    root = root_cls(label="root")
    t0 = time.perf_counter()
    out = render(root, session)
    dt = time.perf_counter() - t0
    assert out.count('class="level-') == depth, f"expected {depth} levels, got: {out!r}"
    return dt


def main() -> None:
    bench_depth(2)  # warmup + sanity

    for depth in DEPTHS:
        dt = bench_depth(depth)
        print(
            f"depth={depth:5d}  {dt * 1000:8.2f} ms  {dt * 1000 / depth:6.3f} ms/level"
        )


if __name__ == "__main__":
    main()
