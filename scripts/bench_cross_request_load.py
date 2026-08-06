"""Cross-request load-cache benchmark: when does tier 2 pay for itself?

The load cache's whole value is skipping the author's load() on a later request,
so what it saves is whatever load() costs — which for any real app is a database
round-trip, not a constructor call. Benchmarking it against a load() that does
nothing measures the wrong thing twice over: it prices the backend's own
overhead against approximately zero, and reports a wash where production would
see a query disappear.

So the simulated cost of load() is the swept variable here. Each row holds the
component count fixed and asks the same question at a different load() cost:
does routing through the backend beat re-running load() on the next request?
The crossover is the number to read — under it, tier 2 costs more than it saves.

time.sleep() stands in for the I/O. It releases the GIL the way a real socket
wait does, so it models a query the process is blocked on rather than one it is
burning CPU over.

Not a CI test (timing-sensitive). Run manually before/after load-cache work:

    uv run python scripts/bench_cross_request_load.py
"""

import os
import statistics
import tempfile
import time
from typing import Annotated

from pyjinhx.config import PjxSettings, configure_pyjinhx
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.session import request_scope

# Milliseconds one load() call blocks for. 0.0 is the pure-overhead case: what
# tier 2 costs when it saves nothing at all.
LOAD_COSTS_MS = (0.0, 0.1, 0.5, 2.0, 10.0)
# Distinct keys per request, so a request pays this many load() calls.
ROWS = 20
REQUESTS = 8

if os.environ.get("PJX_BENCH_SMOKE"):
    LOAD_COSTS_MS = LOAD_COSTS_MS[:1]
    ROWS = 2
    REQUESTS = 2

_load_cost_s = 0.0
_calls = 0


class BenchRow(ReactiveComponent, react={"bench_rows"}):
    """A keyed reactive component whose load() blocks like a query would."""

    row_id: Annotated[int, PjxKey()]
    title: str = ""

    @classmethod
    def load(cls, row_id: int) -> "BenchRow":
        global _calls
        _calls += 1
        if _load_cost_s:
            time.sleep(_load_cost_s)
        return cls(row_id=row_id, title=f"row {row_id}")


def one_request() -> float:
    """Load every row inside a fresh request scope; answer seconds elapsed.

    A new scope per call drops the request-scoped tier-1 store, so a repeat only
    avoids load() if the process-wide backend answered.
    """
    started = time.perf_counter()
    with request_scope():
        for row_id in range(ROWS):
            BenchRow.load(row_id=row_id)
    return time.perf_counter() - started


def measure(cost_ms: float, backend: object | None) -> tuple[float, int]:
    """Median warm-request time in ms, and how many load() bodies actually ran."""
    global _load_cost_s, _calls
    _load_cost_s = cost_ms / 1000
    configure_pyjinhx(PjxSettings(cache_backend=backend))
    _calls = 0
    # The first request is the cold one that fills the cache; the median of what
    # follows is what a steady-state request costs.
    elapsed = [one_request() for _ in range(REQUESTS)]
    return statistics.median(elapsed[1:]) * 1000, _calls


def main() -> None:
    from pyjinhx.integrations.diskcache import DiskCacheBackend

    print(f"{ROWS} load() calls per request, {REQUESTS} requests, fresh scope each")
    print("warm = median of requests 2+\n")
    header = (
        f"{'load() cost':>12}  {'no backend':>11}  {'diskcache':>11}  "
        f"{'saved':>8}  {'load() ran':>11}"
    )
    print(header)
    for cost_ms in LOAD_COSTS_MS:
        plain, plain_calls = measure(cost_ms, None)
        # A fresh directory per row, so one row's warm entries can never answer
        # the next row's cold measurement.
        cached, cached_calls = measure(
            cost_ms, DiskCacheBackend(tempfile.mkdtemp(prefix="pjx-bench-"))
        )
        saved = (plain - cached) / plain * 100 if plain else 0.0
        print(
            f"{cost_ms:10.1f}ms  {plain:9.2f}ms  {cached:9.2f}ms  "
            f"{saved:6.0f}%  {plain_calls:5d} / {cached_calls:<5d}"
        )
    print()
    print("load() ran: bodies executed without a backend / with one.")
    print("A working tier 2 shows the second number at one per distinct key.")


if __name__ == "__main__":
    from _bench_profiling import run_with_optional_profile

    run_with_optional_profile(main)
