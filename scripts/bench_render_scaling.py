"""Render-scaling benchmark for issue #240: N rows x 3 plain cells via PJXTable.

Not a CI test (timing-sensitive). Run manually before/after render-path work:

    uv run python scripts/bench_render_scaling.py
    uv run python scripts/bench_render_scaling.py --profile
"""

import cProfile
import io
import logging
import pstats
import sys
import tempfile
import time

import pyjinhx_v0.builtins.ui  # noqa: F401 — registers builtins
from pyjinhx_v0 import Renderer
from pyjinhx_v0.registry import Registry

logging.getLogger("pyjinhx_v0").setLevel(logging.ERROR)

ROW_COUNTS = (50, 100, 200, 438)


def make_source(rows: int) -> str:
    parts = ['<PJXTable id="t"><PJXTableBody id="tb">']
    for r in range(rows):
        parts.append(
            f'<PJXTableRow id="r{r}">'
            f'<PJXTableCell id="c{r}a"><select><option>choice {r}</option></select></PJXTableCell>'
            f'<PJXTableCell id="c{r}b"><textarea>note {r}</textarea></PJXTableCell>'
            f'<PJXTableCell id="c{r}c"><input type="text" value="v{r}"/></PJXTableCell>'
            f"</PJXTableRow>"
        )
    parts.append("</PJXTableBody></PJXTable>")
    return "".join(parts)


def render(renderer: Renderer, rows: int) -> str:
    with Registry.request_scope():
        return renderer.render(make_source(rows))


def main() -> None:
    Renderer.set_default_environment(tempfile.mkdtemp())
    renderer = Renderer.get_default_renderer()

    out = render(renderer, 2)  # warmup + sanity
    assert "note 1" in out

    for n in ROW_COUNTS:
        t0 = time.perf_counter()
        render(renderer, n)
        dt = time.perf_counter() - t0
        print(f"rows={n:4d}  {dt * 1000:8.1f} ms  {dt * 1000 / n:6.2f} ms/row")

    if "--profile" in sys.argv:
        profiler = cProfile.Profile()
        profiler.enable()
        render(renderer, 438)
        profiler.disable()
        for sort_key in ("cumulative", "tottime"):
            stream = io.StringIO()
            pstats.Stats(profiler, stream=stream).sort_stats(sort_key).print_stats(25)
            print(stream.getvalue())


if __name__ == "__main__":
    main()
