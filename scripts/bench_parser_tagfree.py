"""Attribute VerbatimParser.feed() time between tag-free scanning and markup events.

Subtask #909 (story #907). The question is narrow: of the time html.parser's
goahead() loop spends inside one VerbatimParser.feed(), how much is spent
crossing runs of text that contain no `<` at all - the only bytes a finer
fast path could ever skip - versus handling real tag and entity events, which
any correct parser must do regardless.

cProfile cannot answer that on its own: goahead() is a single loop and its
tag-free scanning is not a separate call frame. So the split is recovered by a
density sweep instead. Payloads of a fixed total byte size are built at varying
tag densities (bytes of inert filler per real tag). Feed time is then a line in
two variables, and its two coefficients are the two buckets the story asks for:

    feed_time(bytes, tags) ~= a * bytes + b * tags

`a` is the marginal per-byte cost of moving over inert text; `b` is the fixed
per-tag cost of an event. At the 65KB shape the benchmark actually renders,
a*bytes is the fast-path headroom and b*tags is inherent per ADR 0005.

Not a CI test (timing-sensitive). Run manually:

    uv run python scripts/bench_parser_tagfree.py
"""

import os
import statistics
import time

from pyjinhx.segments import VerbatimParser

TOTAL_BYTES = 65536
REPEATS = 7

# Bytes of tag-free filler between consecutive real component tags. The sweep
# spans dense markup (one tag every ~48 bytes, roughly what make_payload in
# bench_slot_payload.py emits) up to near-inert text, holding total size fixed
# so only the tag count moves.
FILLER_RUNS = (48, 128, 512, 2048, 8192, 32768)

SIZES = (4096, TOTAL_BYTES)

# CI runs these only to prove they still execute (tests/test_bench_scripts_smoke.py);
# timings are meaningless at one point, so the sweep collapses to its smallest.
if os.environ.get("PJX_BENCH_SMOKE"):
    FILLER_RUNS = FILLER_RUNS[:1]
    SIZES = SIZES[:1]
    REPEATS = 1


def make_density_payload(total_bytes: int, filler_run: int) -> tuple[str, int]:
    """``total_bytes`` of markup with one real component tag per ``filler_run`` bytes.

    Returns the markup and its exact tag count. The filler is prose-like text
    with no `<` in it at all - that is the definition of the bucket being
    measured, so a stray `<` would contaminate the reading. It does contain an
    entity ref and an apostrophe so the tag-free run is not pathologically
    uniform, which would let the interpreter's scan look faster than real
    content.

    When ``filler_run`` approaches or exceeds ``total_bytes`` (the two widest
    entries in ``FILLER_RUNS`` at the 4KB size), the single-chunk floor below
    means the returned markup is longer than ``total_bytes`` requested - there
    is always at least one full chunk. That is fine: the caller records
    ``len(markup)`` as the actual byte count for the regression, not the
    requested ``total_bytes``, so the fit stays honest; it just means those
    rows collapse toward one data point (tag count 1) rather than sweeping
    density cleanly at the small size.
    """
    tag = '<BenchLeaf id="x" class="c"/>'
    filler_unit = "lorem ipsum dolor sit amet &amp; consectetur's adipiscing elit. "
    chunk = tag + filler_unit * max(1, filler_run // len(filler_unit))
    count = max(1, total_bytes // len(chunk))
    markup = chunk * count
    return markup, count


def time_feed(markup: str, repeats: int) -> float:
    """Median seconds for one VerbatimParser feed+close over ``markup``.

    Median, not mean: a single GC pause on a 65KB feed skews a mean by more
    than the effect being measured. A fresh parser per repeat because
    VerbatimParser.feed rebuilds ``_source`` and ``_line_starts`` per call and
    accumulates into ``segments`` - reusing one would measure list growth.
    """
    samples = []
    for _ in range(repeats):
        parser = VerbatimParser()
        t0 = time.perf_counter()
        parser.feed(markup)
        parser.close()
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples)


def fit_two_buckets(points: list[tuple[int, int, float]]) -> tuple[float, float]:
    """Least-squares fit of ``t = a*bytes + b*tags`` over (bytes, tags, seconds).

    Two unknowns, no intercept: there is no fixed per-feed overhead worth
    modelling next to a 65KB scan, and forcing one through the origin keeps the
    coefficients directly readable as "cost per byte of inert text" and "cost
    per tag event".
    """
    sxx = sum(b * b for b, _, _ in points)
    sxy = sum(b * g for b, g, _ in points)
    syy = sum(g * g for _, g, _ in points)
    sxt = sum(b * t for b, _, t in points)
    syt = sum(g * t for _, g, t in points)
    det = sxx * syy - sxy * sxy
    if det == 0:
        return 0.0, 0.0
    return (sxt * syy - syt * sxy) / det, (syt * sxx - sxt * sxy) / det


def main() -> None:
    # Warmup: the first VerbatimParser.feed() call pays one-time costs (attribute
    # lookup caches, allocator growth) that later calls don't - burn that off on
    # a throwaway feed so it doesn't skew the first row of the swept table below.
    warmup_markup, _ = make_density_payload(1024, 128)
    time_feed(warmup_markup, 1)

    points: list[tuple[int, int, float]] = []
    print(f"feed() cost vs tag density, {REPEATS} repeats, median reported:")
    print(
        f"{'bytes':>8}  {'filler run':>11}  {'tags':>6}  {'feed':>10}  {'ns/byte':>9}"
    )
    for size in SIZES:
        for filler_run in FILLER_RUNS:
            markup, tags = make_density_payload(size, filler_run)
            dt = time_feed(markup, REPEATS)
            points.append((len(markup), tags, dt))
            print(
                f"{len(markup):8d}  {filler_run:11d}  {tags:6d}  "
                f"{dt * 1000:8.3f}ms  {dt * 1e9 / len(markup):9.2f}"
            )

    per_byte, per_tag = fit_two_buckets(points)
    dense, dense_tags = make_density_payload(TOTAL_BYTES, 48)
    scan = per_byte * len(dense)
    events = per_tag * dense_tags
    total = scan + events
    print()
    print(f"per inert byte: {per_byte * 1e9:.3f} ns")
    print(f"per tag event:  {per_tag * 1e9:.1f} ns")
    if total > 0:
        print(
            f"at {len(dense)} bytes / {dense_tags} tags: "
            f"{scan / total * 100:.1f}% scan-attributable, "
            f"{events / total * 100:.1f}% event-attributable"
        )


if __name__ == "__main__":
    main()
