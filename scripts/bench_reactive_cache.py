"""Load-cache benchmark: the cost of indexing and evicting cache entries.

bench_reactive_fanout.py measures walk_manifest() and the memoization wrapper;
neither exercises the index bookkeeping that cache_put() and invalidate() do
underneath. Two costs live there:

  1. cache_put(), which un-indexes whatever entry it replaces and then writes
     the entry into one reverse bucket and one forward bucket per reactive key.
  2. invalidate(), which collects the entries a dirtied key names and un-indexes
     each of them - the step that used to walk every bucket in the reverse index
     per entry, making a full eviction quadratic in the number of cached entries.

This script sweeps the number of cached entries so the two should trace straight
lines: doubling N should roughly double each column, not quadruple it.

Not a CI test (timing-sensitive). Run manually before/after load-cache work:

    uv run python scripts/bench_reactive_cache.py
"""

import os
import time

from pyjinhx.reactive.cache import cache_put, invalidate
from pyjinhx.session import request_scope

ENTRY_COUNTS = (500, 1000, 2000, 4000, 8000)

# CI runs these only to prove they still execute (tests/test_bench_scripts_smoke.py);
# timings are meaningless at one point, so the sweep collapses to its smallest.
if os.environ.get("PJX_BENCH_SMOKE"):
    ENTRY_COUNTS = ENTRY_COUNTS[:1]
# Every entry also carries a shared key, so one invalidate() evicts all of them.
SHARED_KEY = "all"


class BenchWidget:
    """Stand-in component class; cache keys only need a hashable type."""


def bench_puts(n: int) -> float:
    """Time filling an empty cache with ``n`` entries, two reactive keys each."""
    with request_scope():
        t0 = time.perf_counter()
        for i in range(n):
            cache_put(BenchWidget, i, f"value {i}", react_keys=(f"key:{i}", SHARED_KEY))
        return time.perf_counter() - t0


def bench_repurs(n: int) -> float:
    """Time re-putting every entry, which un-indexes each one before rewriting."""
    with request_scope():
        for i in range(n):
            cache_put(BenchWidget, i, f"value {i}", react_keys=(f"key:{i}", SHARED_KEY))
        t0 = time.perf_counter()
        for i in range(n):
            cache_put(
                BenchWidget, i, f"redone {i}", react_keys=(f"key:{i}", SHARED_KEY)
            )
        return time.perf_counter() - t0


def bench_invalidate_all(n: int) -> float:
    """Time evicting every entry at once through the shared reactive key."""
    with request_scope():
        for i in range(n):
            cache_put(BenchWidget, i, f"value {i}", react_keys=(f"key:{i}", SHARED_KEY))
        t0 = time.perf_counter()
        invalidate([SHARED_KEY])
        return time.perf_counter() - t0


def main() -> None:
    print("load-cache indexing cost by number of cached entries:")
    print(f"{'n':>6}  {'put':>12}  {'re-put':>12}  {'invalidate all':>16}")
    for n in ENTRY_COUNTS:
        put = bench_puts(n)
        reput = bench_repurs(n)
        evict = bench_invalidate_all(n)
        print(
            f"{n:6d}  {put * 1000:10.2f}ms  {reput * 1000:10.2f}ms  "
            f"{evict * 1000:14.2f}ms"
        )


if __name__ == "__main__":
    from _bench_profiling import run_with_optional_profile

    run_with_optional_profile(main)
