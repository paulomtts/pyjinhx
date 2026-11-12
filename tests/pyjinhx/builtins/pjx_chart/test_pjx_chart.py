"""PJXChart renders a line or bar chart as server-side SVG, with its data as a table."""

import re

import pytest
from pydantic import ValidationError

import pyjinhx.builtins
from pyjinhx.builtins import PJXChart, PJXChartSeries
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

LABELS = ["Jan", "Feb", "Mar", "Apr"]
SALES = PJXChartSeries(name="Sales", values=[4, 8, 6, 10])
COSTS = PJXChartSeries(name="Costs", values=[3, 5, None, 7])


def _html(**kw) -> str:
    kw.setdefault("labels", LABELS)
    kw.setdefault("series", [SALES])
    return render(PJXChart(id="c", **kw), RenderSession())


def _floats(pattern: str, html: str) -> list[float]:
    return [float(v) for v in re.findall(pattern, html)]


def test_is_exported_lazily_from_builtins():
    assert "PJXChart" in pyjinhx.builtins.__all__
    assert "PJXChartSeries" in pyjinhx.builtins.__all__
    assert pyjinhx.builtins._lazy_imports["PJXChart"] == (
        "pyjinhx.builtins.ui.pjx_chart.pjx_chart",
        "PJXChart",
    )
    assert pyjinhx.builtins._lazy_imports["PJXChartSeries"] == (
        "pyjinhx.builtins.ui.pjx_chart.series",
        "PJXChartSeries",
    )


def test_ships_a_stylesheet_and_no_script():
    descriptor = PJXChart.__pjx_descriptor__
    assert [p.name for p in descriptor.css_paths] == ["pjx_chart.css"]
    assert descriptor.js_paths == ()


def test_no_old_theme_attribute():
    css = PJXChart.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")
    assert "data-pjx-theme" in css
    assert "data-theme=" not in css


def test_root_is_a_figure_with_the_kind_class():
    html = _html()
    assert html.startswith('<figure id="c" class="pjx-chart pjx-chart--line"')
    assert 'class="pjx-chart pjx-chart--bar"' in _html(kind="bar")


def test_class_name_and_extra_attrs_land_on_the_root():
    html = _html(class_name="wide", extra_attrs={"hx-get": "/sales"})
    assert html.startswith(
        '<figure id="c" class="pjx-chart pjx-chart--line wide" style="--pjx-chart-height: 240px" aria-label="Chart" hx-get="/sales">'
    )


def test_title_is_the_caption_and_the_accessible_name():
    html = _html(title="Monthly sales")
    assert '<figcaption class="pjx-chart__title">Monthly sales</figcaption>' in html
    assert "<caption>Monthly sales</caption>" in html
    assert "aria-label=" not in html.split(">", 1)[0]


def test_untitled_chart_is_named_by_aria_label():
    html = _html(aria_label="Ventas")
    assert "<figcaption" not in html
    assert 'aria-label="Ventas"' in html
    assert "<caption>Ventas</caption>" in html


def test_svg_is_hidden_from_assistive_tech_and_sized_by_height():
    html = _html(height=200)
    assert 'style="--pjx-chart-height: 200px"' in html
    assert '<svg class="pjx-chart__svg" aria-hidden="true" focusable="false">' in html


def test_data_table_has_a_row_per_label_and_a_column_per_series():
    html = _html(series=[SALES, COSTS])
    table = html[html.index("<table") : html.index("</table>")]
    assert re.findall(r'<th scope="col">([^<]*)</th>', table) == ["", "Sales", "Costs"]
    assert re.findall(r'<th scope="row">([^<]*)</th>', table) == LABELS
    assert re.findall(r"<td>([^<]*)</td>", table) == [
        "4", "3", "8", "5", "6", "", "10", "7",
    ]  # fmt: skip


def test_line_y_axis_ticks_span_the_data_not_zero():
    html = _html()
    assert re.findall(r'class="pjx-chart__y-label"[^>]*>([^<]*)<', html) == [
        "4", "5", "6", "7", "8", "9", "10",
    ]  # fmt: skip
    # Higher values sit higher up: SVG y grows downward.
    ys = _floats(r'<line class="pjx-chart__grid" x1="0" x2="100%" y1="([^"]*)%"', html)
    assert ys == sorted(ys, reverse=True)


def test_positions_are_percentages_of_the_plot():
    html = _html()
    labels = re.findall(
        r'<text class="pjx-chart__x-label" x="([^"]*)"[^>]*>([^<]*)<', html
    )
    assert labels == [
        ("12.5%", "Jan"),
        ("37.5%", "Feb"),
        ("62.5%", "Mar"),
        ("87.5%", "Apr"),
    ]
    cys = re.findall(r'class="pjx-chart__point" cx="[^"]*" cy="([^"]*)"', html)
    assert cys == ["100.0%", "33.33%", "66.67%", "0.0%"]  # 4, 8, 6, 10 on 4..10


def test_lines_are_drawn_in_a_stretched_viewbox():
    html = _html()
    assert (
        '<svg class="pjx-chart__stretch" viewBox="0 0 100 100" preserveAspectRatio="none"'
        in html
    )
    path = re.search(r'class="pjx-chart__line" d="([^"]*)"', html)
    assert path and path.group(1) == "M12.5 100.0 L37.5 33.33 L62.5 66.67 L87.5 0.0"


def test_a_single_line_series_gets_an_area_wash():
    html = _html()
    area = re.search(r'class="pjx-chart__area" d="([^"]*)"', html)
    assert area and area.group(1).startswith("M12.5 100.0 L12.5 100.0 L37.5 33.33")
    assert area.group(1).endswith("L87.5 100.0 Z")
    assert "pjx-chart__area" not in _html(series=[SALES, COSTS])
    assert "pjx-chart__area" not in _html(kind="bar")


def test_many_labels_mark_the_chart_dense():
    many = [str(i) for i in range(25)]
    dense = _html(
        labels=many, series=[PJXChartSeries(name="s", values=list(range(25)))]
    )
    assert 'class="pjx-chart pjx-chart--line pjx-chart--dense"' in dense
    assert "pjx-chart--dense" not in _html()


def test_line_draws_one_path_and_a_point_per_value():
    html = _html()
    assert html.count('class="pjx-chart__line"') == 1
    assert html.count('class="pjx-chart__point"') == 4
    path = re.search(r'class="pjx-chart__line" d="([^"]*)"', html)
    assert path and path.group(1).count("M") == 1 and path.group(1).count("L") == 3


def test_a_missing_value_breaks_the_line():
    html = _html(series=[COSTS])
    path = re.search(r'class="pjx-chart__line" d="([^"]*)"', html)
    assert path and path.group(1).count("M") == 2
    assert html.count('class="pjx-chart__point"') == 3


def test_each_mark_has_a_native_tooltip():
    html = _html(series=[SALES, COSTS])
    titles = re.findall(r"<title>([^<]*)</title>", html)
    assert "Feb · Sales: 8" in titles
    assert "Apr · Costs: 7" in titles
    assert len(titles) == 7


def test_series_take_numbered_classes_in_order():
    many = [PJXChartSeries(name=f"s{i}", values=[1, 2, 3, 4]) for i in range(8)]
    html = _html(series=many)
    groups = re.findall(r'<g class="pjx-chart__series pjx-chart__series--(\d)"', html)
    assert groups == ["1", "2", "3", "4", "5", "6", "7", "8"]


def test_a_ninth_series_is_refused_not_given_a_repeated_colour():
    many = [PJXChartSeries(name=f"s{i}", values=[1, 2, 3, 4]) for i in range(9)]
    with pytest.raises(ValidationError):
        PJXChart(labels=LABELS, series=many)


def _bars(html: str) -> list[tuple[float, float, float, float]]:
    found = re.findall(
        r'<rect class="pjx-chart__bar" x="([^"]*)%" y="([^"]*)%" width="([^"]*)%" height="([^"]*)%"',
        html,
    )
    return [tuple(float(v) for v in bar) for bar in found]  # pyright: ignore[reportReturnType]


def test_bars_are_grouped_and_rise_from_zero():
    html = _html(kind="bar", series=[SALES, COSTS])
    bars = _bars(html)
    assert len(bars) == 7  # the missing value draws no bar
    assert len({w for _, _, w, _ in bars}) == 1
    # Every bar ends on the zero line, the bottom of a 0..10 axis.
    assert {round(y + h, 2) for _, y, _, h in bars} == {100.0}
    # Sales then Costs inside each 25% band, with air on both sides.
    sales, costs = bars[0], bars[4]
    assert 0 < sales[0] < costs[0] and costs[0] + costs[2] < 25
    assert 'rx="3"' in html


def test_negative_bars_hang_below_zero():
    loss = PJXChartSeries(name="Net", values=[5, -5])
    html = _html(kind="bar", labels=["a", "b"], series=[loss])
    (zero,) = re.findall(
        r'class="pjx-chart__zero" x1="0" x2="100%" y1="([^"]*)%"', html
    )
    (_, up_y, _, up_h), (_, down_y, _, _) = _bars(html)
    assert round(up_y + up_h, 2) == float(zero)
    assert down_y == float(zero)


def test_big_ticks_are_compact_but_tooltips_are_full():
    big = PJXChartSeries(name="Revenue", values=[12000, 25000, 1500000, 40000])
    html = _html(series=[big])
    ticks = re.findall(r'class="pjx-chart__y-label"[^>]*>([^<]*)<', html)
    assert ticks[:2] == ["0", "200K"] and ticks[-1] == "1.6M"
    assert "Mar · Revenue: 1,500,000" in html
    assert "<td>1,500,000</td>" in html


def test_bar_scale_always_includes_zero():
    html = _html(kind="bar", series=[PJXChartSeries(name="s", values=[50, 60, 70, 80])])
    labels = re.findall(r'class="pjx-chart__y-label"[^>]*>([^<]*)<', html)
    assert labels[0] == "0"


def test_explicit_y_range_fixes_the_axis_and_clamps_marks():
    html = _html(y_min=0, y_max=5)
    labels = re.findall(r'class="pjx-chart__y-label"[^>]*>([^<]*)<', html)
    assert labels == ["0", "1", "2", "3", "4", "5"]
    ys = _floats(r'class="pjx-chart__point" cx="[^"]*" cy="([^"]*)%"', html)
    assert min(ys) == 0.0  # the plot top: values over 5 stay inside it


def test_legend_lists_series_only_when_there_are_several():
    assert "pjx-chart__legend" not in _html()
    html = _html(series=[SALES, COSTS])
    assert re.findall(r'<li class="pjx-chart__legend-item pjx-chart__series--(\d)">([^<]*)<', html) == [
        ("1", "Sales"), ("2", "Costs"),
    ]  # fmt: skip
    assert "pjx-chart__legend" not in _html(series=[SALES, COSTS], legend=False)


def test_text_is_escaped():
    hostile = '"><script>x</script>'
    html = _html(
        title=hostile,
        labels=[hostile, "b", "c", "d"],
        series=[PJXChartSeries(name=hostile, values=[1, 2, 3, 4])],
    )
    assert "<script>x" not in html
    assert "&lt;script&gt;" in html


def test_all_missing_values_still_render_an_axis():
    blank = PJXChartSeries(name="s", values=[None, None])
    html = _html(labels=["a", "b"], series=[blank])
    assert 'class="pjx-chart__point"' not in html
    assert re.findall(r'class="pjx-chart__y-label"[^>]*>([^<]*)<', html)[0] == "0"


def test_each_series_needs_a_value_per_label():
    with pytest.raises(ValidationError, match="Sales has 4 values for 3 labels"):
        PJXChart(labels=["a", "b", "c"], series=[SALES])


def test_y_min_must_be_below_y_max():
    with pytest.raises(ValidationError, match="y_min must be below y_max"):
        PJXChart(labels=LABELS, series=[SALES], y_min=5, y_max=5)


@pytest.mark.parametrize(
    "kw",
    [
        {"labels": []},
        {"series": []},
        {"kind": "pie"},
        {"height": 40},
    ],
)
def test_rejects_bad_props(kw):
    kw = {"labels": LABELS, "series": [SALES], **kw}
    with pytest.raises(ValidationError):
        PJXChart(**kw)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_series_reject_non_finite_values(bad):
    with pytest.raises(ValidationError):
        PJXChartSeries(name="s", values=[1, bad])


def test_series_are_frozen():
    with pytest.raises(ValidationError):
        SALES.name = "x"  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize("kw", [{"y_min": 50}, {"y_max": -50}])
def test_one_fixed_end_past_all_the_data_still_renders(kw):
    html = _html(**kw)
    assert len(re.findall(r'class="pjx-chart__y-label"', html)) >= 2
    assert html.count('class="pjx-chart__point"') == 4


def _x_labels(html: str) -> list[tuple[str, str]]:
    """Each x label's text and whether it is minor (hidden on a narrow chart)."""
    return [
        (text, minor)
        for minor, text in re.findall(
            r'<text class="pjx-chart__x-label( pjx-chart__x-label--minor)?"[^>]*>([^<]*)<',
            html,
        )
    ]


@pytest.mark.parametrize(
    ("count", "shown", "minor"),
    [(6, 6, 0), (12, 12, 6), (24, 12, 6), (60, 12, 6)],
)
def test_crowded_x_labels_are_thinned(count, shown, minor):
    labels = [f"d{i}" for i in range(count)]
    data = PJXChartSeries(name="s", values=[1.0] * count)
    found = _x_labels(_html(labels=labels, series=[data]))
    assert len(found) == shown
    assert sum(1 for _, m in found if m) == minor
    assert found[0] == ("d0", "")  # the first label always shows


def test_a_lone_bar_series_leaves_more_air_than_a_group():
    lone = _bars(_html(kind="bar"))
    grouped = _bars(_html(kind="bar", series=[SALES, COSTS]))
    band = 25.0
    assert lone[0][2] <= band * 0.5
    assert grouped[0][2] * 2 <= band * 0.7
