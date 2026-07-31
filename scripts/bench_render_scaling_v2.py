"""Render-scaling benchmark for the pyjinhx2 kernel: N independent childless components.

L0 has no child composition, so the sweep is over N separate root-level render()
calls rather than N nested children of one tree.

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

from pyjinhx2.component import BaseComponent
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession

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


TEMPLATE_NAME = "bench_component.pjx"
TEMPLATE_SOURCE = '<div class="bench">{{ label }}</div>'


class BenchComponent(BaseComponent):
    label: str = "bench"


def setup_session() -> RenderSession:
    """Write the benchmark template to a temp dir and point a session at it."""
    template_dir = Path(tempfile.mkdtemp())
    (template_dir / TEMPLATE_NAME).write_text(TEMPLATE_SOURCE)
    # render() reads __pjx_descriptor__ and hands template_path straight to the
    # Jinja loader, which resolves names relative to template_dir — so the path
    # recorded here must stay relative.
    BenchComponent.__pjx_descriptor__ = ClassDescriptor(
        template_path=Path(TEMPLATE_NAME),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": BenchComponent},
    )
    return RenderSession(template_dir=str(template_dir))


def render_one(session: RenderSession, index: int) -> str:
    """Construct one component and render it, returning its markup."""
    component = BenchComponent(label=f"item {index}")
    return render(component, session)


def main() -> None:
    session = setup_session()

    out = render_one(session, 1)  # warmup + sanity
    assert "item 1" in out, f"unexpected warmup output: {out!r}"

    for n in COMPONENT_COUNTS:
        t0 = time.perf_counter()
        for i in range(n):
            render_one(session, i)
        dt = time.perf_counter() - t0
        print(f"n={n:4d}  {dt * 1000:8.1f} ms  {dt * 1000 / n:6.2f} ms/component")

    if "--profile" in sys.argv:
        profiler = cProfile.Profile()
        profiler.enable()
        for i in range(COMPONENT_COUNTS[-1]):
            render_one(session, i)
        profiler.disable()
        for sort_key in ("cumulative", "tottime"):
            stream = io.StringIO()
            pstats.Stats(profiler, stream=stream).sort_stats(sort_key).print_stats(25)
            print(stream.getvalue())


if __name__ == "__main__":
    main()
