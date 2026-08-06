"""Cross-request cache benchmark: does tier 2 actually save the second request?

Every other bench script renders its tree once, inside one scope. That prices
tier 2's write path with no read ever, which is the half of the story that makes
a configured backend look like nothing but overhead — and it is why a render key
that could never repeat went unnoticed: nothing here asked for the same thing
twice.

This script renders the same tree in a fresh request_scope() each time, so tier
1 starts empty and only the process-wide backend can answer. A working render
cache shows request 2 well under request 1; a broken one shows them equal, which
is the shape to watch for.

Not a CI test (timing-sensitive). Run manually before/after cache work:

    uv run python scripts/bench_cross_request_cache.py
    PJX_BENCH_BACKEND=diskcache uv run python scripts/bench_cross_request_cache.py
"""

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_render_scaling_v2 import (
    BenchRoot,
    setup_session,
    tree_shape,
    tree_size,
)

from pyjinhx.config import PjxSettings, configure_pyjinhx
from pyjinhx.reactive.backend import InMemoryCacheBackend
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession, request_scope

COMPONENT_COUNTS = (50, 200, 1000, 5000)
REQUESTS = 12

if os.environ.get("PJX_BENCH_SMOKE"):
    COMPONENT_COUNTS = COMPONENT_COUNTS[:1]
    REQUESTS = 3


def build_backend(name: str | None) -> object | None:
    """The backend named by ``PJX_BENCH_BACKEND``, or None to leave tier 2 off.

    ``diskcache`` is the one that costs a real pickle and a SQLite round-trip;
    ``memory`` isolates the seam's own bookkeeping from that storage cost.
    """
    if name is None or name == "none":
        return None
    if name == "memory":
        return InMemoryCacheBackend()
    if name == "diskcache":
        from pyjinhx.integrations.diskcache import DiskCacheBackend

        return DiskCacheBackend(tempfile.mkdtemp(prefix="pjx-bench-"))
    raise SystemExit(f"unknown PJX_BENCH_BACKEND {name!r}: none, memory or diskcache")


def one_request(session: RenderSession, mids: int, leaves: int) -> float:
    """Render the tree inside a fresh request scope; answer seconds elapsed.

    A new scope per call is the whole point: it drops the request-scoped tier-1
    store, so a repeat render can only be answered by the process-wide backend.
    """
    started = time.perf_counter()
    with request_scope(session=session):
        render(BenchRoot(mids=mids, leaves=leaves), session)
    return time.perf_counter() - started


def main() -> None:
    name = os.environ.get("PJX_BENCH_BACKEND")
    backend = build_backend(name)
    if backend is not None:
        configure_pyjinhx(PjxSettings(cache_backend=backend))

    session = setup_session()
    print(f"backend={name or 'none'}, {REQUESTS} requests per size, fresh scope each\n")
    print(
        f"{'n':>6}  {'request 1':>11}  {'request 2':>11}  {'median 3+':>11}  {'1/warm':>8}"
    )
    for requested in COMPONENT_COUNTS:
        mids, leaves = tree_shape(requested)
        n = tree_size(mids, leaves)
        elapsed = [one_request(session, mids, leaves) for _ in range(REQUESTS)]
        cold = elapsed[0] * 1000
        second = elapsed[1] * 1000
        # Median of the rest rather than the mean: one scheduler hiccup in a
        # dozen requests should not decide the number this is read for.
        warm = statistics.median(elapsed[2:]) * 1000
        print(
            f"{n:6d}  {cold:9.1f}ms  {second:9.1f}ms  {warm:9.1f}ms  {cold / warm:7.2f}x"
        )


if __name__ == "__main__":
    from _bench_profiling import run_with_optional_profile

    run_with_optional_profile(main)
