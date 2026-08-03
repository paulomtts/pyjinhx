"""Render-scaling benchmark for the pyjinhx kernel: one nested component tree per size.

L1 composition is in: a parent's rendered ChildRef holes are filled and recursed
into, so the sweep renders a real tree rather than N independent root renders.
The tree is three levels deep — BenchRoot -> many BenchMid siblings -> many
BenchLeaf siblings under each mid — with breadth scaled per size to hit the
requested component count. That is the shape a real page has (a few structural
layers, many repeated leaves), and distinct classes per level keep the
ancestor-chain cycle guard out of the measurement.

Not a CI test (timing-sensitive). Run manually before/after render-path work:

    uv run python scripts/bench_render_scaling_v2.py
    uv run python scripts/bench_render_scaling_v2.py --profile
"""

import cProfile
import io
import math
import pstats
import sys
import tempfile
import time
from pathlib import Path

from pyjinhx import discovery
from pyjinhx.component import BaseComponent
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.render import render
from pyjinhx.session import RenderSession

COMPONENT_COUNTS = (50, 100, 200, 500, 1000, 2000, 5000, 10000)


def tree_shape(n: int) -> tuple[int, int]:
    """Breadth at each level for a 3-level tree of roughly ``n`` components.

    Breadth is split evenly between the two non-root levels so neither depth
    dominates the reading. An exact ``n`` is not always reachable with integer
    breadths, so the shape rounds and the caller prints the count it actually
    built.
    """
    mids = max(1, math.isqrt(max(n - 1, 1)))
    leaves = max(0, round((n - 1 - mids) / mids))
    return mids, leaves


def tree_size(mids: int, leaves: int) -> int:
    """Total component count for a shape: root + mids + leaves under each mid."""
    return 1 + mids + mids * leaves


TEMPLATES = {
    "bench_root.pjx": (
        '<div class="bench-root">'
        "{% for i in range(mids) %}"
        '<BenchMid label="mid {{ i }}" leaves="{{ leaves }}"/>'
        "{% endfor %}"
        "</div>"
    ),
    "bench_mid.pjx": (
        '<section class="bench-mid">{{ label }}'
        "{% for j in range(leaves) %}"
        '<BenchLeaf label="leaf {{ j }}"/>'
        "{% endfor %}"
        "</section>"
    ),
    "bench_leaf.pjx": '<em class="bench-leaf">{{ label }}</em>',
}


class BenchLeaf(BaseComponent):
    label: str = "leaf"


class BenchMid(BaseComponent):
    label: str = "mid"
    leaves: int = 0


class BenchRoot(BaseComponent):
    mids: int = 0
    leaves: int = 0


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


def setup_session() -> RenderSession:
    """Write the three bench templates to a temp dir, attach descriptors, publish
    the tag registry, and point a session at the dir.

    The registry is poked directly instead of going through build_registry: the
    classes live in this script, not on disk under a package, and the benchmark
    is measuring render, not discovery.
    """
    template_dir = Path(tempfile.mkdtemp())
    for name, source in TEMPLATES.items():
        (template_dir / name).write_text(source)
    # render() hands template_path straight to the Jinja loader, which resolves
    # names relative to template_dir — so these paths must stay relative.
    BenchRoot.__pjx_descriptor__ = _descriptor(BenchRoot, "bench_root.pjx")
    BenchMid.__pjx_descriptor__ = _descriptor(BenchMid, "bench_mid.pjx")
    BenchLeaf.__pjx_descriptor__ = _descriptor(BenchLeaf, "bench_leaf.pjx")
    discovery._registry.mapping = {
        "bench_root": BenchRoot,
        "bench_mid": BenchMid,
        "bench_leaf": BenchLeaf,
    }
    return RenderSession(template_dir=str(template_dir))


def render_tree(session: RenderSession, mids: int, leaves: int) -> str:
    """Build one whole nested tree of the given shape and render it once."""
    return render(BenchRoot(mids=mids, leaves=leaves), session)


def main() -> None:
    session = setup_session()

    out = render_tree(session, 2, 2)  # warmup + sanity
    assert '<em class="bench-leaf">leaf 1</em>' in out, f"unexpected warmup: {out!r}"

    for requested in COMPONENT_COUNTS:
        mids, leaves = tree_shape(requested)
        n = tree_size(mids, leaves)
        t0 = time.perf_counter()
        render_tree(session, mids, leaves)
        dt = time.perf_counter() - t0
        print(f"n={n:6d}  {dt * 1000:8.1f} ms  {dt * 1000 / n:6.3f} ms/component")

    if "--profile" in sys.argv:
        mids, leaves = tree_shape(COMPONENT_COUNTS[-1])
        profiler = cProfile.Profile()
        profiler.enable()
        render_tree(session, mids, leaves)
        profiler.disable()
        for sort_key in ("cumulative", "tottime"):
            stream = io.StringIO()
            pstats.Stats(profiler, stream=stream).sort_stats(sort_key).print_stats(25)
            print(stream.getvalue())


if __name__ == "__main__":
    main()
