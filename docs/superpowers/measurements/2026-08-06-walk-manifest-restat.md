# walk_manifest re-stat: before/after measurements

Verification for story #888. The fix under measurement is the request-scoped
template-freshness cache wired into `AbsolutePathLoader.uptodate()` and
`render_level()`. No production code changed in this pass; the numbers below
were taken on `origin/master` with those commits present.

## cProfile — walk_manifest(), n=5000, 100% dirty, cumulative sort

| | total wall time | time in is_up_to_date / stat | share |
| --- | --- | --- | --- |
| before | 4.26s | 3.98s | ~93% |
| after | 0.837s | 0.002s (session.py `uptodate`) | ~0.2% |

Top cumulative frames after the fix:

```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        8    0.000    0.000    1.505    0.188 threading.py:1058(join)
        8    0.000    0.000    1.505    0.188 {method 'join' of '_thread._ThreadHandle' objects}
        1    0.001    0.001    0.857    0.857 pyjinhx/reactive/fanout.py:560(walk_manifest)
5000/2715    0.007    0.000    0.803    0.000 pyjinhx/segments.py:157(feed)
5000/2715    0.003    0.000    0.799    0.000 html/parser.py:153(feed)
```

The stat/uptodate-matching frames, separately:

```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
     5000    0.007    0.000    0.030    0.000 pyjinhx/reactive/component.py:78(state_hash)
4997/2136    0.003    0.000    0.002    0.000 pyjinhx/session.py:75(uptodate)
      7/4    0.000    0.000    0.000    0.000 pathlib/_local.py:510(stat)
      7/4    0.000    0.000    0.000    0.000 {built-in method posix.stat}
```

`is_up_to_date`/`uptodate`/`stat` no longer appear anywhere near the top of
the cumulative list; `posixpath.stat` is called 7 times total (not once per
manifest entry), and the request-scoped `uptodate()` closure's own cumtime is
0.002s against a 0.837s total run. Wall time for the whole profiled call
dropped from 4.26s to 0.837s.

## bench_reactive_fanout.py — bench_walk(), 100%-dirty column

| n | before | after (run 1) | after (run 2) |
| --- | --- | --- | --- |
| 50 | 17.36ms | 2.47ms | 2.50ms |
| 5000 | 273.95ms | 226.83ms | 224.00ms |

Full walk_manifest table, run 1:

```
     n    0% dirty   50% dirty  100% dirty
    50       0.18ms       7.30ms       2.47ms
   100       0.33ms       2.56ms       4.61ms
   200       0.64ms       4.90ms       9.17ms
   500       1.67ms      12.30ms      22.90ms
  1000       3.28ms      24.44ms      42.70ms
  2000       6.38ms      46.61ms      86.12ms
  5000      15.91ms     117.13ms     226.83ms
```

Two runs are reported because the script is timing-sensitive and manual-only;
its numbers are not asserted in CI.

## Conclusion

The memoization eliminated the per-render re-stat cost as intended: the
`is_up_to_date`/`uptodate`/`stat` chain dropped from ~93% of a 4.26s profiled
run to a 0.002s cumtime inside a 0.837s run, and bench_walk's 100%-dirty
column fell by roughly 7x at n=50 (17.36ms to ~2.5ms) and by roughly 18% at
n=5000 (273.95ms to ~225ms).
