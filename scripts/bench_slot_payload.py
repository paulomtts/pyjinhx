"""Render benchmark: slot/children payload SIZE, at a fixed component count.

bench_render_scaling_v2.py sweeps component *count* with tiny per-component
payloads, and bench_render_depth.py sweeps nesting depth at breadth 1. Neither
moves the number of *bytes* flowing through a level, so two size-driven costs
are invisible in both: VerbatimParser.feed (pyjinhx/segments.py), which scans
every character of a level's rendered markup and rebuilds a line-start index
over it, and _splice_slot_nodes (pyjinhx/render.py), which walks each string
segment looking for slot placeholder tokens. This script pins the component
count and sweeps payload size instead, so any super-linear cost in bytes shows
up on its own axis.

Two arms per size, sharing one payload generator:

  * children: the payload rides in as a paired tag's body text, which reaches
    the child through _instantiate_child's children-field merge.
  * slot: the payload rides in as a list of leaf *component instances*
    assigned directly to a Slot-typed field (not authored as markup attrs,
    which always arrive as plain strings and would never reach
    _splice_slot_nodes at all — see build_slot_arm below), so the parent's
    render emits one placeholder token per leaf that _splice_slot_nodes must
    find and replace.

Distinct dynamically-named classes per arm keep render_level's ancestor-chain
cycle guard (ADR 0004) out of the reading, as in bench_render_depth.py.

Not a CI test (timing-sensitive). Run manually before/after parse or slot work:

    uv run python scripts/bench_slot_payload.py
    uv run python scripts/bench_slot_payload.py --profile
"""

import cProfile
import io
import os
import pstats
import sys
import tempfile
import time
from pathlib import Path

from pyjinhx import discovery
from pyjinhx._component import BaseComponent, Children, Slot, _pascal_to_snake
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

FIXED_COMPONENTS = 50
PAYLOAD_BYTES = (64, 256, 1024, 4096, 16384, 65536)

# CI runs these only to prove they still execute (tests/test_bench_scripts_smoke.py);
# timings are meaningless at one point, so the sweep collapses to its smallest.
if os.environ.get("PJX_BENCH_SMOKE"):
    PAYLOAD_BYTES = PAYLOAD_BYTES[:1]


def make_payload(size: int, index: int) -> str:
    """Markup-ish filler of roughly ``size`` bytes, unique per index.

    Real markup rather than a flat run of one character: the parser's cost is
    driven by tag and entity events, not by raw length alone, so filler with no
    tags in it would understate feed().
    """
    unit = f'<span class="fill-{index}">payload {index} </span>'
    return unit * max(1, size // len(unit))


def _descriptor(
    cls: type[BaseComponent], template: str, template_dir: Path
) -> ClassDescriptor:
    """Minimal descriptor pointing at a temp-dir template."""
    slot_fields = frozenset(
        name for name in cls.model_fields if name in {"body", "panel"}
    )
    return ClassDescriptor(
        template_path=template_dir / template,
        slot_fields=slot_fields,
        children_field="body" if "body" in cls.model_fields else None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


def build_children_arm(template_dir: Path) -> type[BaseComponent]:
    """Root whose N children each receive the payload as tag body text."""
    leaf = type(
        "BenchSlotPayloadChildrenLeaf",
        (BaseComponent,),
        {"body": "", "__annotations__": {"body": Children}},
    )
    root = type(
        "BenchSlotPayloadChildrenRoot",
        (BaseComponent,),
        {"payload": "", "count": 0, "__annotations__": {"payload": str, "count": int}},
    )
    (template_dir / "bench_slot_payload_children_leaf.pjx").write_text(
        '<div class="leaf">{{ body }}</div>'
    )
    (template_dir / "bench_slot_payload_children_root.pjx").write_text(
        '<div class="root">{% for i in range(count) %}'
        "<BenchSlotPayloadChildrenLeaf>{{ payload }}</BenchSlotPayloadChildrenLeaf>"
        "{% endfor %}</div>"
    )
    for cls, template in (
        (leaf, "bench_slot_payload_children_leaf.pjx"),
        (root, "bench_slot_payload_children_root.pjx"),
    ):
        cls.__pjx_descriptor__ = _descriptor(cls, template, template_dir)
        discovery._registry.mapping[_pascal_to_snake(cls.__name__)] = cls
    return root


def build_slot_arm(
    template_dir: Path,
) -> tuple[type[BaseComponent], type[BaseComponent]]:
    """Root whose slot field holds a *list of leaf component instances*.

    Only a component-valued slot ever reaches _splice_slot_nodes: the finalize
    hook (pyjinhx/markers.py:finalize_slot_node) swaps in a placeholder token
    only for a ComponentNode, and build_context._wrap_slot_value only wraps a
    Slot-typed field's value when it is actually a BaseComponent (or a
    list/dict of them) — never a plain str. A payload authored as markup
    attrs (``<Leaf panel="{{ payload }}"/>``) always arrives as a string via
    ChildRef.attrs (pyjinhx/render.py's own docstring: "A tag attribute
    always arrives as a string"), so that shape would never produce a token
    and _splice_slot_nodes would no-op on it — indistinguishable from the
    children arm and not what this script claims to isolate. The leaves are
    therefore built directly in Python, one per payload, and assigned as a
    list to the root's Slot field, so render_context wraps each with a
    ComponentNode and the parent's ``{% for item in items %}{{ item }}`` loop
    emits one placeholder token per leaf for _splice_slot_nodes to resolve.
    """
    leaf = type(
        "BenchSlotPayloadSlotLeaf",
        (BaseComponent,),
        {"payload": "", "__annotations__": {"payload": str}},
    )
    root = type(
        "BenchSlotPayloadSlotRoot",
        (BaseComponent,),
        {"items": [], "__annotations__": {"items": Slot}},
    )
    (template_dir / "bench_slot_payload_slot_leaf.pjx").write_text(
        '<div class="leaf">{{ payload }}</div>'
    )
    (template_dir / "bench_slot_payload_slot_root.pjx").write_text(
        '<div class="root">{% for item in items %}{{ item }}{% endfor %}</div>'
    )
    leaf.__pjx_descriptor__ = _descriptor(
        leaf, "bench_slot_payload_slot_leaf.pjx", template_dir
    )
    root.__pjx_descriptor__ = ClassDescriptor(
        template_path=template_dir / "bench_slot_payload_slot_root.pjx",
        slot_fields=frozenset({"items"}),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": root},
    )
    discovery._registry.mapping[_pascal_to_snake(leaf.__name__)] = leaf
    discovery._registry.mapping[_pascal_to_snake(root.__name__)] = root
    return root, leaf


def bench_children(
    root_cls: type[BaseComponent], session: RenderSession, size: int
) -> float:
    """Render one tree of FIXED_COMPONENTS children carrying ``size``-byte payloads."""
    root = root_cls(payload=make_payload(size, 0), count=FIXED_COMPONENTS)
    t0 = time.perf_counter()
    out = render(root, session)
    dt = time.perf_counter() - t0
    assert out.count('class="leaf"') == FIXED_COMPONENTS, "unexpected arm output"
    return dt


def bench_slot(
    root_cls: type[BaseComponent],
    leaf_cls: type[BaseComponent],
    session: RenderSession,
    size: int,
) -> float:
    """Render one tree of FIXED_COMPONENTS slot-carried leaves, ``size`` bytes each."""
    items = [leaf_cls(payload=make_payload(size, i)) for i in range(FIXED_COMPONENTS)]
    root = root_cls(items=items)
    t0 = time.perf_counter()
    out = render(root, session)
    dt = time.perf_counter() - t0
    assert out.count('class="leaf"') == FIXED_COMPONENTS, "unexpected arm output"
    return dt


def main() -> None:
    template_dir = Path(tempfile.mkdtemp())
    discovery._registry.mapping = {}
    children_root = build_children_arm(template_dir)
    slot_root, slot_leaf = build_slot_arm(template_dir)
    session = RenderSession()

    bench_children(children_root, session, 64)  # warmup + sanity
    bench_slot(slot_root, slot_leaf, session, 64)

    print(f"payload size sweep at a fixed {FIXED_COMPONENTS} components per tree:")
    print(f"{'bytes':>8}  {'children':>12}  {'slot':>12}  {'us/KB (children)':>18}")
    for size in PAYLOAD_BYTES:
        children = bench_children(children_root, session, size)
        slot = bench_slot(slot_root, slot_leaf, session, size)
        per_kb = children * 1e6 / max(1.0, size * FIXED_COMPONENTS / 1024)
        print(
            f"{size:8d}  {children * 1000:10.2f}ms  {slot * 1000:10.2f}ms  {per_kb:16.2f}"
        )

    if "--profile" in sys.argv:
        profiler = cProfile.Profile()
        profiler.enable()
        bench_children(children_root, session, PAYLOAD_BYTES[-1])
        bench_slot(slot_root, slot_leaf, session, PAYLOAD_BYTES[-1])
        profiler.disable()
        for sort_key in ("cumulative", "tottime"):
            stream = io.StringIO()
            pstats.Stats(profiler, stream=stream).sort_stats(sort_key).print_stats(25)
            print(stream.getvalue())


if __name__ == "__main__":
    from _bench_profiling import run_with_optional_profile

    run_with_optional_profile(main)
