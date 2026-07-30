"""The v2 benchmark script is not timed in CI, but it must keep importing and rendering."""

import importlib.util
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


def test_bench_script_renders_one_component():
    bench = load_bench_module()
    session = bench.setup_session()
    out = bench.render_one(session, 7)
    assert "item 7" in out
    assert '<div class="bench">' in out


def test_bench_sweep_sizes_match_v1():
    bench = load_bench_module()
    assert bench.COMPONENT_COUNTS == (50, 100, 200, 438)
