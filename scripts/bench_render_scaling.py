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
import time

import pyjinhx.builtins  # noqa: F401 — registers builtins
from pyjinhx._component import BaseComponent, Slot
from pyjinhx.builtins.pjx_table import PJXTable
from pyjinhx.builtins.pjx_table_body import PJXTableBody
from pyjinhx.builtins.pjx_table_cell import PJXTableCell
from pyjinhx.builtins.pjx_table_row import PJXTableRow
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

logging.getLogger("pyjinhx").setLevel(logging.ERROR)

ROW_COUNTS = (50, 100, 200, 438)


class _RowsHost(BaseComponent):
    """Sibling-list wrapper so multiple child instances share one field."""

    content: Slot = ""


def make_table(rows: int) -> PJXTable:
    row_items = [
        PJXTableRow(
            id=f"r{r}",
            content=_RowsHost(
                id=f"cells-r{r}",
                content=[
                    PJXTableCell(id=f"c{r}a", content=f"choice {r}"),
                    PJXTableCell(id=f"c{r}b", content=f"note {r}"),
                    PJXTableCell(id=f"c{r}c", content=f"v{r}"),
                ],
            ),
        )
        for r in range(rows)
    ]
    return PJXTable(
        id="t",
        content=PJXTableBody(id="tb", content=_RowsHost(id="rows", content=row_items)),
    )


def render_rows(rows: int) -> str:
    return render(make_table(rows), RenderSession())


def main() -> None:
    out = render_rows(2)  # warmup + sanity
    assert "note 1" in out

    for n in ROW_COUNTS:
        t0 = time.perf_counter()
        render_rows(n)
        dt = time.perf_counter() - t0
        print(f"rows={n:4d}  {dt * 1000:8.1f} ms  {dt * 1000 / n:6.2f} ms/row")

    if "--profile" in sys.argv:
        profiler = cProfile.Profile()
        profiler.enable()
        render_rows(438)
        profiler.disable()
        for sort_key in ("cumulative", "tottime"):
            stream = io.StringIO()
            pstats.Stats(profiler, stream=stream).sort_stats(sort_key).print_stats(25)
            print(stream.getvalue())


if __name__ == "__main__":
    main()
