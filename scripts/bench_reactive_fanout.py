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

Not a CI test (timing-sensitive). Run manually before/after reactive-path work:

    uv run python scripts/bench_reactive_fanout.py
"""

import dataclasses
import tempfile
import time
from pathlib import Path
from typing import Annotated

from pyjinhx2 import discovery, registry
from pyjinhx2.reactive.cache import cache_put
from pyjinhx2.reactive.component import PjxKey, ReactiveComponent
from pyjinhx2.reactive.fanout import walk_manifest
from pyjinhx2.session import request_scope

MANIFEST_SIZES = (50, 100, 200, 500, 1000, 2000, 5000)
DIRTY_RATIOS = (0.0, 0.5, 1.0)  # all-clean, half-dirty, all-dirty


class BenchReactiveWidget(ReactiveComponent, react=("bench",)):
    """A reactive component keyed by ``pjx_key``; load() does real-ish work."""

    pjx_key: Annotated[str, PjxKey()] = ""

    def load(self) -> str:
        return f"data:{self.pjx_key}"


def setup_registry() -> str:
    """Publish a tag -> class map and point the descriptor at a temp template.

    Mirrors bench_render_scaling_v2.py: the registry is poked directly since
    the class lives in this script, not on disk under a package.
    """
    template_dir = Path(tempfile.mkdtemp())
    (template_dir / "bench_reactive_widget.pjx").write_text("<div>{{ pjx_key }}</div>")
    discovery.build_registry(template_dir, [BenchReactiveWidget])
    BenchReactiveWidget.__pjx_descriptor__ = dataclasses.replace(
        BenchReactiveWidget.__pjx_descriptor__,
        template_path=Path("bench_reactive_widget.pjx"),
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
    with request_scope(template_dir):
        manifest = make_manifest(n, dirty_ratio, template_dir)
        t0 = time.perf_counter()
        walk_manifest(manifest, {"bench"})
        return time.perf_counter() - t0


def bench_memoization(template_dir: str) -> tuple[float, float]:
    """Cold vs. warm load() calls on the same instance, one request scope."""
    with request_scope(template_dir):
        instance = BenchReactiveWidget(id="memo", pjx_key="1")
        t0 = time.perf_counter()
        instance.load()
        cold = time.perf_counter() - t0
        t0 = time.perf_counter()
        instance.load()
        warm = time.perf_counter() - t0
    return cold, warm


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


if __name__ == "__main__":
    main()
