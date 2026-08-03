"""Benchmark: state_hash() on its own, off the render path.

state_hash() (pyjinhx/reactive/component.py) is three costs stacked —
model_dump(mode="json"), a sorted json.dumps, and a SHA-256 over the encoded
result. Today it is only ever timed inside walk_manifest() in
bench_reactive_fanout.py, where a load() call and a full render_level() dwarf
it, so a regression in the hash itself would hide inside that noise. This
script calls state_hash() directly, in a loop, with no session and no render.

Two axes, swept independently so a dump-driven cost and an encode/digest-driven
cost cannot be confused:

  * field count at a fixed small value per field — moves model_dump's per-field
    work and the number of keys json.dumps must sort.
  * value size at a fixed field count — moves the encoded byte count that
    json.dumps writes and SHA-256 consumes, with the field loop held constant.

Each field count builds a distinct dynamically-named class, so no reading is
taken against a class pydantic has already warmed for a different shape.

Not a CI test (timing-sensitive). Run manually before/after state-hash work:

    uv run python scripts/bench_state_hash.py
"""

import time

from pyjinhx.reactive.component import ReactiveComponent

FIELD_COUNTS = (5, 20, 50, 100)
VALUE_SIZES = (16, 256, 4096, 65536)
ITERATIONS = 200


def build_class(label: str, fields: int) -> type[ReactiveComponent]:
    """A ReactiveComponent with ``fields`` str fields, uniquely named per shape."""
    namespace: dict[str, object] = {"__annotations__": {}}
    for i in range(fields):
        namespace[f"f{i}"] = ""
        namespace["__annotations__"][f"f{i}"] = str  # type: ignore[index]
    return type(f"BenchStateHash{label}{fields}", (ReactiveComponent,), namespace)


def bench(instance: ReactiveComponent) -> float:
    """Mean seconds per state_hash() call over ITERATIONS calls."""
    instance.state_hash()  # warmup: first call pays pydantic's dump setup
    t0 = time.perf_counter()
    for _ in range(ITERATIONS):
        instance.state_hash()
    return (time.perf_counter() - t0) / ITERATIONS


def main() -> None:
    print("state_hash() by field count (16-byte values):")
    print(f"{'fields':>7}  {'us/call':>10}  {'us/field':>10}")
    for fields in FIELD_COUNTS:
        cls = build_class("Fields", fields)
        instance = cls(id="h", **{f"f{i}": "x" * 16 for i in range(fields)})
        dt = bench(instance)
        print(f"{fields:7d}  {dt * 1e6:8.2f}  {dt * 1e6 / fields:8.3f}")
    print()

    print("state_hash() by value size (10 fields):")
    print(f"{'bytes':>8}  {'us/call':>10}  {'us/KB':>10}")
    for size in VALUE_SIZES:
        cls = build_class("Sizes", 10)
        instance = cls(id="h", **{f"f{i}": "x" * size for i in range(10)})
        dt = bench(instance)
        print(f"{size:8d}  {dt * 1e6:8.2f}  {dt * 1e6 / (size * 10 / 1024):8.2f}")


if __name__ == "__main__":
    main()
