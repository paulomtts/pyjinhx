"""Doc-lint: the chart guide matches the shipped chart.

The guide's code blocks are code a reader copies, and its tables name props,
classes and tokens by hand, so these run the blocks as written and check the
names against the sources.
"""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from pyjinhx.builtins import PJXChart, PJXChartSeries

_ROOT = Path(__file__).resolve().parents[2]
_GUIDE = _ROOT / "docs" / "guide" / "chart.md"
_CHART = _ROOT / "pyjinhx" / "builtins" / "ui" / "pjx_chart"
_SOURCES = (_CHART / "pjx_chart.css", _CHART / "pjx_chart.pjx")

# Built from the data by the component, never passed by the app.
_DERIVED = {"y_ticks", "x_ticks", "zero_y", "dense", "marks", "rows"}
# Every component takes these; the guide says so once instead of per table.
_COMMON = {"id", "class_name", "extra_attrs"}


def _guide() -> str:
    return _GUIDE.read_text(encoding="utf-8")


def _sources() -> str:
    return "".join(p.read_text(encoding="utf-8") for p in _SOURCES)


def test_every_python_block_runs():
    blocks = re.findall(r"```python\n(.*?)```", _guide(), flags=re.DOTALL)
    assert blocks
    for block in blocks:
        exec(compile(block, str(_GUIDE), "exec"), {})  # noqa: S102 — the published snippets


def test_the_quick_start_route_serves_a_self_refreshing_chart():
    block = re.search(r"## Quick start\n\n```python\n(.*?)```", _guide(), re.DOTALL)
    assert block
    namespace: dict = {}
    exec(compile(block.group(1), str(_GUIDE), "exec"), namespace)  # noqa: S102 — the published snippet
    html = TestClient(namespace["app"]).get("/traffic").text
    assert '<figure id="traffic" class="pjx-chart pjx-chart--line"' in html
    assert 'hx-get="/traffic"' in html


def test_every_class_and_token_the_guide_names_exists():
    named = set(re.findall(r"pjx-chart[\w-]*", _guide()))
    # The guide writes the numbered ones as a range.
    named -= {"pjx-chart__series--", "pjx-chart-"}
    sources = _sources()
    assert named
    assert sorted(n for n in named if n not in sources) == []


def test_the_props_tables_list_every_field():
    guide = _guide()
    chart_fields = set(PJXChart.model_fields) - _DERIVED - _COMMON
    series_fields = set(PJXChartSeries.model_fields)
    documented = set(re.findall(r"^\| `(\w+)` \|", guide, flags=re.MULTILINE))
    assert chart_fields | series_fields <= documented
    assert documented <= chart_fields | series_fields


def test_the_theming_notes_use_only_theme_names():
    guide = _guide()
    assert "data-theme" not in guide
    legacy = re.findall(r"(?<![\w-])--(?:surface|text|border|brand)\b[\w-]*", guide)
    assert legacy == []
