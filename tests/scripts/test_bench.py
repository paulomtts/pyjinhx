"""Every benchmark script must still run, even though CI never times one.

Five of the nine scripts under `scripts/` were silently broken for two
milestones: #735 (absolute-path Jinja loader) left four of them building a
`template_path` from a bare filename, and #725 (`load()` became a classmethod
factory) migrated builtins, docs and examples but not this directory. Nothing
noticed, because "not in CI (timing-sensitive)" had been read as "not in CI".

Timing is what cannot be asserted here; *running* is not. Each script collapses
its sweep to the smallest entry when `PJX_BENCH_SMOKE` is set, so this executes
the whole path — build classes, write templates, render, assert its own shape —
without measuring anything."""

import importlib.util
import itertools
import os
import pkgutil
import subprocess
import sys
from pathlib import Path

import pytest

import pyjinhx.builtins
from pyjinhx.components.base import BaseComponent
from pyjinhx.components.discovery import build_registry
from pyjinhx.rendering.pipeline import render as v2_render
from pyjinhx.rendering.session import RenderSession
from tests.fixtures.bench.bench_builtin_heavy import (
    V0_MANIFEST,
    V2_MANIFEST,
    build_v0_page,
    build_v2_page,
    build_v2_table,
    component_names,
)

SCRIPTS_DIR = Path(__file__).parents[2] / "scripts"
BENCH_SCRIPTS = sorted(p.name for p in SCRIPTS_DIR.glob("bench_*.py"))

# A smoke run is one point per sweep; the slowest is well under a second. The
# ceiling is here to fail loudly rather than hang a CI job if one regresses into
# doing real work.
TIMEOUT_SECONDS = 120


def test_every_bench_script_is_discovered():
    """Guards the glob itself: a rename that empties it must not pass silently."""
    assert len(BENCH_SCRIPTS) >= 9, BENCH_SCRIPTS


@pytest.mark.parametrize("script", BENCH_SCRIPTS)
def test_bench_script_runs(script: str):
    env = {**os.environ, "PJX_BENCH_SMOKE": "1"}
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        env=env,
        cwd=SCRIPTS_DIR.parent,
        # Not check=True: the assertion below reports the script's own traceback,
        # which is the whole point. CalledProcessError would hide it.
        check=False,
    )
    assert result.returncode == 0, (
        f"{script} exited {result.returncode}\n"
        f"--- stdout ---\n{result.stdout[-2000:]}\n"
        f"--- stderr ---\n{result.stderr[-2000:]}"
    )
    assert result.stdout.strip(), f"{script} produced no output"


@pytest.mark.parametrize("script", BENCH_SCRIPTS)
def test_bench_script_honours_the_smoke_flag(script: str):
    """Without the collapse, a smoke run would be a full sweep and time out.

    Asserted on the source rather than by timing: the point is that the guard
    exists in every script, so a new one cannot join the suite and quietly make
    it slow.
    """
    source = (SCRIPTS_DIR / script).read_text(encoding="utf-8")
    assert "PJX_BENCH_SMOKE" in source, (
        f"{script} has no smoke guard; add one so CI can run it cheaply"
    )


# The v2 benchmark script is not timed in CI, but it must keep importing and rendering.


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


# Cheap CI guard: the v0.36 and v2 bench pages must reference the same components.
#
# Not timing-sensitive — no rendering happens here, only manifest comparison,
# except for `test_v2_table_cell_content_stays_raw_html` below, which does
# render (a single small table) to pin the fixed str-Slot behavior (see
# bench_builtin_heavy's module docstring) — #686 restored ADR 0003's
# raw-HTML-capable Slot invariant, so this now matches v0's rendering.


def test_manifests_are_the_same_logical_component_set() -> None:
    assert V0_MANIFEST == V2_MANIFEST


def test_manifest_is_not_trivially_small() -> None:
    # Guards against someone gutting the page to make the bench look good.
    assert len(V0_MANIFEST) >= 20


def test_every_manifest_entry_appears_in_both_page_sources() -> None:
    """Every manifest tag is a substring of v0's markup, and a class in v2's tree.

    v0's page is a flat markup string (its native shape); v2's page is a real
    component instance tree (see bench_builtin_heavy's module docstring for
    why) — so the two sides are checked differently, but assert the same
    thing: every manifest entry is actually present on both sides.
    """
    v0_src = build_v0_page(rows=3)
    v2_names = component_names(build_v2_page(rows=3))
    for logical in V0_MANIFEST:
        assert logical in v0_src, f"{logical} missing from v0 page source"
    for logical in V2_MANIFEST:
        assert logical in v2_names, f"{logical} missing from v2 page tree"


def _v2_registry() -> None:
    """Import every builtin module and register the discovered classes.

    Mirrors scripts/bench_v0_vs_v2.py's `_import_all_v2_builtins` /
    `_v2_all_classes` / `build_registry` sequence — needed here because this
    test actually renders, unlike the manifest-only tests above.
    """
    for module_info in pkgutil.walk_packages(
        pyjinhx.builtins.__path__, prefix="pyjinhx.builtins."
    ):
        __import__(module_info.name)
    found: list[type] = []
    stack = list(BaseComponent.__subclasses__())
    while stack:
        cls = stack.pop()
        found.append(cls)
        stack.extend(cls.__subclasses__())
    build_registry("pyjinhx/builtins", found)


def test_v2_table_cell_content_stays_raw_html() -> None:
    """v2's table cell renders its raw-HTML Slot value raw, matching v0.

    #686 restored ADR 0003's invariant that a plain-`str` Slot value is
    raw-HTML-capable: `_wrap_slot_value` now wraps it in `markupsafe.Markup`
    after retrieval, so pydantic's plain-`str` coercion on assignment (which
    strips `Markup`'s `__html__` protocol) is no longer in the way.
    """
    _v2_registry()
    html = v2_render(build_v2_table(rows=1), RenderSession())
    assert '<input type="text" value="v0"/>' in html
    assert "&lt;input" not in html
