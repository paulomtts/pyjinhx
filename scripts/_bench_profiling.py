"""Opt-in cProfile wrapper shared by the bench_*.py scripts.

Off by default: profiling overhead would distort the very wall-clock numbers
these scripts exist to measure. Set PJX_BENCH_PROFILE to turn it on for a run.
"""

import cProfile
import os
import pstats
import sys


def run_with_optional_profile(main_fn) -> None:
    """Run ``main_fn()``, profiling under cProfile when PJX_BENCH_PROFILE is set.

    PJX_BENCH_PROFILE_SORT selects the pstats sort key (default "tottime").
    PJX_BENCH_PROFILE_TOP caps how many rows print (default 25). The table
    goes to stderr so it never lands in a redirected/diffed stdout baseline.
    """
    if not os.environ.get("PJX_BENCH_PROFILE"):
        main_fn()
        return

    sort_key = os.environ.get("PJX_BENCH_PROFILE_SORT", "tottime")
    top_n = int(os.environ.get("PJX_BENCH_PROFILE_TOP", "25"))

    profiler = cProfile.Profile()
    profiler.enable()
    try:
        main_fn()
    finally:
        profiler.disable()

    print(
        f"\n{'=' * 88}\ncProfile ({sort_key}, top {top_n})\n{'=' * 88}",
        file=sys.stderr,
    )
    stats = pstats.Stats(profiler, stream=sys.stderr)
    stats.sort_stats(sort_key)
    stats.print_stats(top_n)
