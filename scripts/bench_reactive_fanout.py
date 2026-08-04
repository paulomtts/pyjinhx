"""Reactive-layer benchmark: load-cache memoization and the fan-out walk.

render_scaling_v2.py measures render() with plain BaseComponents; nothing in it
touches ReactiveComponent. Two costs live outside that path entirely:

  1. The load-cache wrap around ReactiveComponent.load() (cheap: a dict lookup
     per call, on top of whatever load()'s body does).
  2. walk_manifest(), which runs *after* render() returns, over the client's
     mounted manifest rather than the tree just rendered — its cost scales
     with "how many components does the client currently have on screen," not
     with how large the render that just happened was. A "clean" candidate
     costs one cache lookup; a "dirty" one costs a real load() + render_level()
     + a state_hash() (model_dump + JSON encode + SHA-256).

This script sweeps manifest size at a few clean/dirty ratios to show how the
walk's cost is driven by the dirty share, not the manifest size alone.

  3. oob_swaps(), the response-body build that runs after the walk: per dirty
     candidate it stamps hx-swap-oob + data-pjx-hash at the recorded root_span
     and serializes the level. Only outerHTML and delete swaps are ever emitted
     (ADR 0001). Swept over region count x per-region subtree size, with the
     levels built before the clock starts so no render is in the frame.
  4. _drop_nested()/_contained(), the containment walk. PR #619 (issue #600)
     made the candidate-count axis linear; the sweep here moves the other axis,
     per-candidate rendered-subtree size, which _contained walks segment by
     segment and which the count sweep holds at a constant.

Not a CI test (timing-sensitive). Run manually before/after reactive-path work:

    uv run python scripts/bench_reactive_fanout.py
"""

import dataclasses
import os
import tempfile
import time
from pathlib import Path
from typing import Annotated

from pyjinhx import discovery, registry
from pyjinhx.reactive.cache import cache_put
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.reactive.fanout import (
    FanoutCandidate,
    _drop_nested,
    oob_swaps,
    walk_manifest,
)
from pyjinhx.rendering import render_level
from pyjinhx.session import RenderSession, request_scope

MANIFEST_SIZES = (50, 100, 200, 500, 1000, 2000, 5000)
DIRTY_RATIOS = (0.0, 0.5, 1.0)  # all-clean, half-dirty, all-dirty
OOB_REGION_COUNTS = (10, 50, 100, 200)
OOB_SUBTREE_SIZES = (1, 10, 50)  # child spans inside each swapped region

# CI runs these only to prove they still execute (tests/test_bench_scripts_smoke.py);
# timings are meaningless at one point, so the sweep collapses to its smallest.
if os.environ.get("PJX_BENCH_SMOKE"):
    MANIFEST_SIZES = MANIFEST_SIZES[:1]
    DIRTY_RATIOS = DIRTY_RATIOS[:1]
    OOB_REGION_COUNTS = OOB_REGION_COUNTS[:1]
    OOB_SUBTREE_SIZES = OOB_SUBTREE_SIZES[:1]

DROP_CANDIDATE_COUNTS = (50, 200)
DROP_SUBTREE_SIZES = (1, 10, 50, 200)

if os.environ.get("PJX_BENCH_SMOKE"):
    DROP_CANDIDATE_COUNTS = DROP_CANDIDATE_COUNTS[:1]
    DROP_SUBTREE_SIZES = DROP_SUBTREE_SIZES[:1]


class BenchReactiveWidget(ReactiveComponent, react=("bench",)):
    """A reactive component keyed by ``pjx_key``; load() does real-ish work."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "BenchReactiveWidget":
        return cls(pjx_key=pjx_key)


class BenchOobWidget(ReactiveComponent, react=("bench",)):
    """A reactive region whose rendered size is driven by ``spans``."""

    pjx_key: Annotated[str, PjxKey()] = ""
    spans: int = 1

    @classmethod
    def load(cls, pjx_key: str) -> "BenchOobWidget":
        return cls(pjx_key=pjx_key)


def setup_registry() -> str:
    """Publish a tag -> class map and point the descriptor at a temp template.

    Mirrors bench_render_scaling_v2.py: the registry is poked directly since
    the class lives in this script, not on disk under a package.
    """
    template_dir = Path(tempfile.mkdtemp())
    (template_dir / "bench_reactive_widget.pjx").write_text("<div>{{ pjx_key }}</div>")
    (template_dir / "bench_oob_widget.pjx").write_text(
        '<div class="oob">{% for i in range(spans) %}'
        '<span class="cell">{{ pjx_key }}-{{ i }}</span>'
        "{% endfor %}</div>"
    )
    discovery.build_registry(template_dir, [BenchReactiveWidget, BenchOobWidget])
    BenchReactiveWidget.__pjx_descriptor__ = dataclasses.replace(
        BenchReactiveWidget.__pjx_descriptor__,
        template_path=template_dir / "bench_reactive_widget.pjx",
    )
    BenchOobWidget.__pjx_descriptor__ = dataclasses.replace(
        BenchOobWidget.__pjx_descriptor__,
        template_path=template_dir / "bench_oob_widget.pjx",
    )
    return str(template_dir)


def make_manifest(n: int, dirty_ratio: float, template_dir: str) -> list[dict]:
    """Build ``n`` manifest entries, registering each so resolve() finds it.

    ``dirty_ratio`` of them are left uncached (walk_manifest re-loads and
    re-renders); the rest have their load-cache entry pre-populated (walk_manifest
    answers "clean" from one cache lookup).
    """
    dirty_count = round(n * dirty_ratio)
    entries = []
    for i in range(n):
        instance_id = f"w{i}"
        load_key = str(i)
        registry.register_instance(
            BenchReactiveWidget.__name__, instance_id, f"resolved:{i}"
        )
        if i >= dirty_count:
            cache_put(
                BenchReactiveWidget, load_key, f"cached:{i}", react_keys=("bench",)
            )
        entries.append(
            {
                "type": "bench_reactive_widget",
                "id": instance_id,
                "load": load_key,
                "hash": "stale-hash",  # never matches a fresh SHA-256, so a
                # dirty candidate always survives the hash gate below.
            }
        )
    return entries


def bench_walk(n: int, dirty_ratio: float, template_dir: str) -> float:
    with request_scope():
        manifest = make_manifest(n, dirty_ratio, template_dir)
        t0 = time.perf_counter()
        walk_manifest(manifest, {"bench"})
        return time.perf_counter() - t0


def bench_memoization(template_dir: str) -> tuple[float, float]:
    """Cold vs. warm load() calls for the same load key, one request scope.

    The memo wrap keys on (class, load key), so the second call for "1" is the
    cache hit — there is no instance to call it on any more.
    """
    with request_scope():
        t0 = time.perf_counter()
        BenchReactiveWidget.load("1")
        cold = time.perf_counter() - t0
        t0 = time.perf_counter()
        BenchReactiveWidget.load("1")
        warm = time.perf_counter() - t0
    return cold, warm


def make_dirty_candidate(
    index: int, subtree: int, session: RenderSession
) -> FanoutCandidate:
    """One dirty candidate carrying a real RenderedLevel of ``subtree`` inner spans.

    oob_swaps() asserts a dirty candidate has both a RenderedLevel and a
    fresh_hash (it stamps data-pjx-hash itself, since the on_rendered stamper
    is not wired onto the dirty path's session), so both are supplied here.
    """
    instance = BenchOobWidget(id=f"oob{index}", pjx_key=str(index), spans=subtree)
    level = render_level(instance, session)
    return FanoutCandidate(
        type_name="bench_oob_widget",
        component_class=BenchOobWidget,
        instance_id=instance.id,
        load=str(index),
        status="dirty",
        entry={},
        level=level,
        instance=instance,
        fresh_hash=instance.state_hash(),
    )


def bench_oob_swaps(regions: int, subtree: int, template_dir: str) -> float:
    """Time oob_swaps() alone: stamping + serializing ``regions`` built levels.

    The levels are built *before* the clock starts, so this reading is pure
    stamp_root_attrs + serialize per region (ADR 0001: outerHTML only, plus
    delete for a missing candidate — no other swap value is ever emitted), with
    no render or load in the frame.
    """
    with request_scope():
        session = RenderSession()
        candidates = [make_dirty_candidate(i, subtree, session) for i in range(regions)]
        t0 = time.perf_counter()
        oob_swaps(candidates)
        return time.perf_counter() - t0


def bench_drop_nested(candidates_n: int, subtree: int, template_dir: str) -> float:
    """Time _drop_nested() over ``candidates_n`` disjoint regions of ``subtree`` spans.

    PR #619 (issue #600) already made the candidate-count axis linear by
    replacing the pairwise scan with two passes over a unioned id/identity set;
    that axis is not re-swept here. What this adds is the other axis: _contained
    walks every segment of every candidate's tree to build the union, so the
    per-candidate cost is driven by how big each rendered region is, which the
    existing sweep holds at a tiny constant. The regions are disjoint siblings,
    so nothing is actually dropped and the full two-pass walk is paid.
    """
    with request_scope():
        session = RenderSession()
        candidates = [
            make_dirty_candidate(i, subtree, session) for i in range(candidates_n)
        ]
        t0 = time.perf_counter()
        survivors = _drop_nested(candidates)
        dt = time.perf_counter() - t0
        assert len(survivors) == candidates_n, (
            f"disjoint regions must all survive, kept {len(survivors)}"
        )
        return dt


def main() -> None:
    template_dir = setup_registry()

    print("load() memoization (single instance, cold vs. warm call):")
    cold, warm = bench_memoization(template_dir)
    print(f"  cold={cold * 1e6:8.1f} us  warm={warm * 1e6:8.1f} us")
    print()

    print("walk_manifest() over the mounted manifest, by size and dirty share:")
    header = f"{'n':>6}  " + "  ".join(
        f"{int(r * 100):>3}% dirty" for r in DIRTY_RATIOS
    )
    print(header)
    for n in MANIFEST_SIZES:
        row = [f"{n:6d}"]
        for ratio in DIRTY_RATIOS:
            dt = bench_walk(n, ratio, template_dir)
            row.append(f"{dt * 1000:9.2f}ms")
        print("  ".join(row))

    print()
    print("oob_swaps() alone: stamp + serialize per dirty region (levels prebuilt):")
    header = f"{'regions':>8}  " + "  ".join(f"{s:>4} spans" for s in OOB_SUBTREE_SIZES)
    print(header)
    for regions in OOB_REGION_COUNTS:
        row = [f"{regions:8d}"]
        for subtree in OOB_SUBTREE_SIZES:
            dt = bench_oob_swaps(regions, subtree, template_dir)
            row.append(f"{dt * 1000:8.2f}ms")
        print("  ".join(row))

    print()
    print("_drop_nested() containment walk, by per-candidate subtree size:")
    header = f"{'subtree':>8}  " + "  ".join(
        f"{n:>5} cands" for n in DROP_CANDIDATE_COUNTS
    )
    print(header)
    for subtree in DROP_SUBTREE_SIZES:
        row = [f"{subtree:8d}"]
        for candidates_n in DROP_CANDIDATE_COUNTS:
            dt = bench_drop_nested(candidates_n, subtree, template_dir)
            row.append(f"{dt * 1000:9.2f}ms")
        print("  ".join(row))


if __name__ == "__main__":
    main()
