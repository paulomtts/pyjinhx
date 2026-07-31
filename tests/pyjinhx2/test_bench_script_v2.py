"""The v2 benchmark script is not timed in CI, but it must keep importing and rendering."""

import importlib.util
import itertools
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "bench_render_scaling_v2.py"


def load_bench_module():
    spec = importlib.util.spec_from_file_location("bench_render_scaling_v2", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # register before exec: BenchComponent's class body resolves its template
    # path from sys.modules[__module__].__file__, which only exists once the
    # module is registered
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bench_renders_a_nested_tree_at_every_level():
    bench = load_bench_module()
    session = bench.setup_session()
    mids, leaves = bench.tree_shape(bench.COMPONENT_COUNTS[0])
    out = bench.render_tree(session, mids, leaves)
    assert '<div class="bench-root">' in out
    assert out.count('<section class="bench-mid">') == mids
    assert out.count('<em class="bench-leaf">') == mids * leaves


def test_tree_shape_is_deterministic_and_close_to_requested_size():
    bench = load_bench_module()
    for n in (50, 100, 200, 500, 1000, 2000, 5000, 10000):
        mids, leaves = bench.tree_shape(n)
        assert mids >= 1
        assert leaves >= 0
        total = 1 + mids + mids * leaves
        assert abs(total - n) <= mids  # rounding slack is at most one leaf per mid
        assert bench.tree_shape(n) == (mids, leaves)  # deterministic


def test_bench_sweep_tops_out_at_ten_thousand():
    bench = load_bench_module()
    counts = bench.COMPONENT_COUNTS
    assert counts[-1] == 10_000
    assert max(counts) == 10_000
    assert all(a < b for a, b in itertools.pairwise(counts))
