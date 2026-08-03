"""v0.36.4 vs v2 comparison on the same builtin-heavy page (issue #537, PRD G2).

Not a CI test (timing-sensitive). Run manually:

    uv run python scripts/bench_v0_vs_v2.py
    uv run python scripts/bench_v0_vs_v2.py --profile

v0.36 side: the in-tree ``pyjinhx_v0/`` package. It is *not* byte-identical to
the ``v0.36.4`` tag on this branch (`git diff --stat v0.36.4..origin/master --
pyjinhx_v0/` is non-empty at the time this was written), so the recorded run
was taken from a separate worktree checked out at the tag itself
(`git worktree add /tmp/pyjinhx_v0-v0364 v0.36.4`) with that path prepended to
``sys.path`` ahead of the in-tree ``pyjinhx_v0/`` package. ``pyjinhx_v0/`` is
deleted by #540, so the numbers this prints get captured into
docs/superpowers/rebuild/roadmap.md rather than re-derived later.

v2 side: the fixture page is a real ``pyjinhx2`` component instance tree
(not a markup string) — see ``tests/fixtures/bench_builtin_heavy.py``'s
module docstring for why a plain nested-tag markup string does not expand
past one custom-tag boundary on this side.
"""

import cProfile
import importlib
import io
import logging
import pkgutil
import pstats
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

_V0364_WORKTREE = Path("/tmp/pyjinhx_v0-v0364")
if _V0364_WORKTREE.is_dir():
    sys.path.insert(0, str(_V0364_WORKTREE))

import pyjinhx2.builtins
import pyjinhx_v0.builtins.ui  # noqa: F401 — registers v0 builtins (import side effect)
from pyjinhx2.component import BaseComponent
from pyjinhx2.discovery import build_registry
from pyjinhx2.render import render as v2_render
from pyjinhx2.session import RenderSession
from pyjinhx_v0 import Renderer as V0Renderer
from pyjinhx_v0.registry import Registry as V0Registry
from tests.fixtures.bench_builtin_heavy import (
    build_v0_page,
    build_v0_shells,
    build_v0_table,
    build_v2_page,
    build_v2_shells,
    build_v2_table,
)

logging.getLogger("pyjinhx_v0").setLevel(logging.ERROR)
logging.getLogger("pyjinhx2").setLevel(logging.ERROR)

ROWS = 200
ITERATIONS = 20


def _import_all_v2_builtins() -> None:
    """Import every module under pyjinhx2.builtins so their classes exist to
    be found by ``__subclasses__()`` — ``import pyjinhx2.builtins`` alone only
    imports the (empty) package ``__init__``, not each builtin submodule."""
    for module_info in pkgutil.walk_packages(
        pyjinhx2.builtins.__path__, prefix="pyjinhx2.builtins."
    ):
        importlib.import_module(module_info.name)


def _v2_all_classes() -> list[type]:
    """Every declared BaseComponent subclass (mirrors config.py:_all_component_classes)."""
    found: list[type] = []
    stack = list(BaseComponent.__subclasses__())
    while stack:
        cls = stack.pop()
        found.append(cls)
        stack.extend(cls.__subclasses__())
    return found


def _v0_renderer() -> V0Renderer:
    V0Renderer.set_default_environment(tempfile.mkdtemp())
    return V0Renderer.get_default_renderer()


def _v0_render(renderer: V0Renderer, source: str) -> str:
    with V0Registry.request_scope():
        return renderer.render(source)


def _v2_render(session: RenderSession, component: BaseComponent) -> str:
    return v2_render(component, session)


def _sanity(label: str, v0_html: str, v2_html: str) -> None:
    """Fail fast, before any timing, if the two sides are not comparable."""
    if not v0_html.strip():
        raise SystemExit(f"[{label}] v0.36 render produced empty output")
    if not v2_html.strip():
        raise SystemExit(f"[{label}] v2 render produced empty output")
    for marker in ('id="r0"', 'id="r1"', 'id="bench-table"'):
        if (marker in v0_html) != (marker in v2_html):
            raise SystemExit(
                f"[{label}] marker {marker} present on only one side — pages are not comparable"
            )
    v0_rows = v0_html.count('id="r')
    v2_rows = v2_html.count('id="r')
    if v0_rows != v2_rows:
        raise SystemExit(
            f"[{label}] row-marker counts differ: v0={v0_rows} v2={v2_rows}"
        )


def _time(fn: Callable[[], object]) -> list[float]:
    """One warmup call, then ITERATIONS timed calls; per-iteration milliseconds."""
    fn()
    times: list[float] = []
    for _ in range(ITERATIONS):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000.0)
    return times


CASES: tuple[tuple[str, Callable[[], str], Callable[[], BaseComponent]], ...] = (
    ("full page", lambda: build_v0_page(ROWS), lambda: build_v2_page(ROWS)),
    ("table rows=200", lambda: build_v0_table(ROWS), lambda: build_v2_table(ROWS)),
    ("shells only", build_v0_shells, build_v2_shells),
)


def main() -> None:
    _import_all_v2_builtins()
    build_registry("pyjinhx2/builtins", _v2_all_classes())

    print(
        f"{'case':<20} {'v0 med':>9} {'v2 med':>9} {'v0 mean':>9} {'v2 mean':>9} "
        f"{'delta ms':>9} {'delta %':>8}"
    )
    v0_renderer = _v0_renderer()
    any_regression = False
    for label, v0_build, v2_build in CASES:
        # One session per case, reused across every iteration of that case's
        # timed loop — matches v0_renderer's reuse below, so neither side pays
        # per-iteration environment-construction cost the other doesn't.
        v2_session = RenderSession(template_dir="/")
        v0_html = _v0_render(v0_renderer, v0_build())
        v2_html = _v2_render(v2_session, v2_build())
        _sanity(label, v0_html, v2_html)

        v0_times = _time(lambda v0_build=v0_build: _v0_render(v0_renderer, v0_build()))
        v2_times = _time(
            lambda v2_session=v2_session, v2_build=v2_build: _v2_render(
                v2_session, v2_build()
            )
        )
        v0_med, v2_med = statistics.median(v0_times), statistics.median(v2_times)
        v0_mean, v2_mean = statistics.mean(v0_times), statistics.mean(v2_times)
        d_ms = v2_med - v0_med
        d_pct = (d_ms / v0_med) * 100.0
        regressed = d_pct > 0.0
        any_regression |= regressed
        print(
            f"{label:<20} {v0_med:9.2f} {v2_med:9.2f} {v0_mean:9.2f} {v2_mean:9.2f} "
            f"{d_ms:+9.2f} {d_pct:+7.1f}%"
        )

    print()
    print(
        "G2: no case regressed"
        if not any_regression
        else "G2: REGRESSION — see rows with positive delta"
    )

    if "--profile" in sys.argv:
        v0_source = build_v0_page(ROWS)
        v2_component = build_v2_page(ROWS)
        profile_session = RenderSession(template_dir="/")
        for side_label, fn in (
            ("v0.36", lambda: _v0_render(v0_renderer, v0_source)),
            ("v2", lambda: _v2_render(profile_session, v2_component)),
        ):
            print(f"=== {side_label} ===")
            profiler = cProfile.Profile()
            profiler.enable()
            fn()
            profiler.disable()
            for sort_key in ("cumulative", "tottime"):
                stream = io.StringIO()
                pstats.Stats(profiler, stream=stream).sort_stats(sort_key).print_stats(
                    25
                )
                print(stream.getvalue())


if __name__ == "__main__":
    main()
