"""The chart in real chromium: its stylesheet's contract and an htmx swap.

The chart has no script, so these check what only a browser can: the SVG
scales to its container, series take their palette token, the data table is
visually hidden yet still in the accessibility tree, and htmx can replace a
chart with a fresh render.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pyjinhx.builtins import PJXChart, PJXChartSeries
from pyjinhx.client import read_vendored_htmx
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

if TYPE_CHECKING:
    from playwright.sync_api import Page

CSS = (
    Path(__file__).resolve().parents[4]
    / "pyjinhx"
    / "builtins"
    / "ui"
    / "pjx_chart"
    / "pjx_chart.css"
).read_text(encoding="utf-8")
URL = "http://pjx.test/"


def _chart(values: list[float | None], **kw) -> str:
    series = [
        PJXChartSeries(name="Sales", values=values),
        PJXChartSeries(name="Costs", values=[1, 1, 1]),
    ]
    return render(
        PJXChart(id="c", labels=["a", "b", "c"], series=series, **kw), RenderSession()
    )


def _open(page: Page, body: str, routes: dict[str, str] | None = None) -> None:
    def fulfill(route) -> None:
        path = route.request.url.removeprefix(URL)
        if path in (routes or {}):
            route.fulfill(content_type="text/html", body=(routes or {})[path])
        else:
            route.fulfill(
                content_type="text/html",
                body=f"<html><head><style>{CSS}</style></head><body>{body}</body></html>",
            )

    page.route(URL + "**", fulfill)
    page.goto(URL)


def test_svg_fills_its_container_at_the_given_height(page, page_errors):
    _open(page, f'<div style="width: 320px">{_chart([1, 2, 3], height=180)}</div>')
    box = page.locator("#c .pjx-chart__svg").bounding_box()
    assert box is not None
    assert round(box["height"]) == 180
    assert 240 <= box["width"] < 320  # the rest is the y labels' gutter
    assert page_errors == []


def test_text_and_strokes_keep_their_size_at_any_width(page, page_errors):
    narrow = _chart([1, 2, 3]).replace('id="c"', 'id="narrow"')
    wide = _chart([1, 2, 3]).replace('id="c"', 'id="wide"')
    _open(
        page,
        f'<div style="width: 300px">{narrow}</div><div style="width: 1200px">{wide}</div>',
    )
    sizes = page.evaluate(
        """() => ['narrow', 'wide'].map((id) => {
            const chart = document.getElementById(id);
            const label = chart.querySelector('.pjx-chart__x-label').getBoundingClientRect();
            const line = getComputedStyle(chart.querySelector('.pjx-chart__line'));
            return [Math.round(label.height), line.vectorEffect, line.strokeWidth];
        })"""
    )
    assert sizes[0] == sizes[1]
    assert sizes[0][1:] == ["non-scaling-stroke", "2px"]
    assert page_errors == []


def test_dark_scheme_takes_the_dark_palette(page, page_errors):
    page.emulate_media(color_scheme="dark")
    _open(page, _chart([1, 2, 3], kind="bar"))
    fill = page.evaluate(
        "() => getComputedStyle(document.querySelector('.pjx-chart__bar')).fill"
    )
    assert fill == "rgb(57, 135, 229)"  # #3987e5, not the light #2a78d6
    assert page_errors == []


def test_hovering_a_series_dims_the_others(page, page_errors):
    _open(page, _chart([1, 2, 3]))
    page.hover("#c .pjx-chart__series--1 .pjx-chart__point >> nth=1")
    page.wait_for_function(
        """() => getComputedStyle(document.querySelector(
            '#c .pjx-chart__series--2')).opacity < 0.5"""
    )
    opacity = page.evaluate(
        """() => getComputedStyle(document.querySelector(
            '#c .pjx-chart__series--1')).opacity"""
    )
    assert opacity == "1"
    assert page_errors == []


def test_series_take_their_palette_token(page, page_errors):
    _open(
        page,
        "<style>:root { --pjx-chart-1: rgb(1, 2, 3); --pjx-chart-2: rgb(4, 5, 6); }</style>"
        + _chart([1, 2, 3], kind="bar"),
    )
    fills = page.evaluate(
        """() => Array.from(document.querySelectorAll('.pjx-chart__bar'),
            (bar) => getComputedStyle(bar).fill)"""
    )
    assert fills == ["rgb(1, 2, 3)"] * 3 + ["rgb(4, 5, 6)"] * 3
    swatch = page.evaluate(
        """() => getComputedStyle(document.querySelector(
            '.pjx-chart__legend-item'), '::before').backgroundColor"""
    )
    assert swatch == "rgb(1, 2, 3)"
    assert page_errors == []


def test_lines_are_stroked_not_filled(page, page_errors):
    _open(
        page,
        "<style>:root { --pjx-chart-1: rgb(1, 2, 3); }</style>" + _chart([1, 2, 3]),
    )
    style = page.evaluate(
        """() => { const s = getComputedStyle(document.querySelector('.pjx-chart__line'));
            return [s.fill, s.stroke]; }"""
    )
    assert style == ["none", "rgb(1, 2, 3)"]
    assert page_errors == []


def test_data_table_is_hidden_but_read(page, page_errors):
    _open(page, _chart([1, 2, 3], title="Sales"))
    box = page.locator("#c .pjx-chart__data").bounding_box()
    assert box is not None and box["width"] <= 1 and box["height"] <= 1
    assert page.get_by_role("table", name="Sales").count() == 1
    assert page.get_by_role("cell", name="2", exact=True).count() == 1
    assert page_errors == []


def test_htmx_swaps_in_a_fresh_render(page, page_errors):
    fresh = _chart([9, 9, 9])
    _open(
        page,
        _chart(
            [1, 2, 3],
            extra_attrs={
                "hx-get": "/fresh",
                "hx-trigger": "load delay:10ms",
                "hx-swap": "outerHTML",
            },
        )
        + f"<script>{read_vendored_htmx()}</script>",
        routes={"fresh": fresh},
    )
    page.wait_for_function(
        """() => document.querySelector('#c .pjx-chart__table td').textContent === '9'"""
    )
    assert page.locator(".pjx-chart").count() == 1
    assert page_errors == []


def test_a_narrow_chart_hides_its_minor_x_labels(page, page_errors):
    months = [f"M{i}" for i in range(12)]
    series = [PJXChartSeries(name="s", values=[1.0] * 12)]
    narrow = render(
        PJXChart(id="narrow", labels=months, series=series), RenderSession()
    )
    wide = render(PJXChart(id="wide", labels=months, series=series), RenderSession())
    _open(
        page,
        f'<div style="width: 300px">{narrow}</div><div style="width: 900px">{wide}</div>',
    )
    shown = page.evaluate(
        """() => ['narrow', 'wide'].map((id) => Array.from(
            document.querySelectorAll('#' + id + ' .pjx-chart__x-label'))
            .filter((label) => label.getBoundingClientRect().width > 0).length)"""
    )
    assert shown == [6, 12]
    assert page_errors == []


def test_a_shrink_to_fit_parent_still_gives_the_chart_room(page, page_errors):
    # Size containment, which the label thinning needs, would otherwise give
    # the chart no width of its own inside a centred grid or flex column.
    _open(
        page,
        f'<div style="display: grid; place-items: center"><div>{_chart([1, 2, 3])}</div></div>',
    )
    box = page.locator("#c").bounding_box()
    assert box is not None and box["width"] >= 280
    assert page_errors == []
