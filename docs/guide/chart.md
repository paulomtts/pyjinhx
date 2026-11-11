# Chart

`PJXChart` draws a line or bar chart on the server as plain SVG. There is no JavaScript: the
chart is ready in the first paint, works with scripts off, and an htmx swap replaces it like any
other markup. The data lives in `PJXChartSeries`, one named row of values per series.
[ADR 0006](../decisions/0006-server-rendered-svg-charts.md) records why it is drawn in Python and
not by a JavaScript charting library.

## Quick start

```python
from fastapi import FastAPI

from pyjinhx import setup
from pyjinhx.builtins import PJXChart, PJXChartSeries

app = FastAPI()
setup(app)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]


@app.get("/traffic")
def traffic():
    return PJXChart(
        id="traffic",
        title="Traffic",
        labels=MONTHS,
        series=[
            PJXChartSeries(name="Visits", values=[120, 180, 150, 210, None, 260]),
            PJXChartSeries(name="Sign-ups", values=[30, 45, 40, 70, 65, 90]),
        ],
        extra_attrs={
            "hx-get": "/traffic",
            "hx-trigger": "every 30s",
            "hx-swap": "outerHTML",
        },
    )
```

The `hx-*` attributes are optional: with them the chart fetches a fresh render of itself every
30 seconds and swaps it in. Any htmx trigger works the same way, because the chart is only
markup.

## PJXChartSeries

One named row of data, a frozen pydantic model.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `str` | required | Shown in the legend, the tooltips and the data table's header. |
| `values` | `list[float \| None]` | required | One value per label. `None` marks a missing value: the line breaks there and the bar is left out. NaN and infinity are rejected. |

## PJXChart

Every builtin also takes `id`, `class_name` and `extra_attrs`; see
[Builtin conventions](builtin-conventions.md).

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `labels` | `list[str]` | required | The x-axis labels, one per data point. |
| `series` | `list[PJXChartSeries]` | required | One to eight. Each must have exactly one value per label. |
| `kind` | `"line"` or `"bar"` | `"line"` | Several bar series are grouped side by side within each label. |
| `title` | `str` | `""` | The visible caption, and the chart's accessible name. |
| `aria_label` | `str` | `"Chart"` | The accessible name when `title` is empty. |
| `legend` | `bool` | `True` | Shows a legend when there are two or more series. A single series has none. |
| `y_min` | `float \| None` | `None` | Fixes the bottom of the y axis. |
| `y_max` | `float \| None` | `None` | Fixes the top of the y axis. Must be above `y_min` when both are set. |
| `height` | `int` | `240` | The plot's height in pixels, at least 80. The width follows the container. |

A series whose length does not match `labels`, an empty `labels`, no series or more than eight, or
an unknown `kind` raises a `pydantic.ValidationError` when the chart is built.

### The y axis

The y axis gets about five round ticks (steps of 1, 2 or 5 times a power of ten) that cover the
data. A line chart's axis follows the data, so it does not have to start at zero; a bar chart's
always includes zero, so bar lengths compare honestly. `y_min` and `y_max` replace either end, and a
mark beyond them is clamped to the edge of the plot. A zero line is drawn whenever zero is on the
axis.

Values print with thousands separators and without float noise: `1234567` as `1,234,567`, `0.1 +
0.2` as `0.3`. An axis that reaches 10,000 shortens its ticks to `200K` or `1.5M`; tooltips and
the data table keep the full value.

### Size and sharpness

The chart fills its container's width at `height` pixels. Every mark is placed as a percentage of
the plot, so text stays at its pixel size and lines stay 2px wide however wide the chart is. A
line chart draws its path in a viewBox stretched to the plot, with `vector-effect:
non-scaling-stroke`, so the stretch never blurs the stroke.

The x axis shows at most twelve labels, always keeping the first, and a chart narrower than 30rem
shows half of those (through a container query). A line chart with more than 24 labels hides its
points until one is hovered. Hovering a series dims the others.

A line chart with a single series gets a faint wash under the line; with several, the washes would
overlap, so there is none. A lone bar series leaves more space between bars than a group does.

The chart is a size container (`container-type: inline-size`). Its `contain-intrinsic-inline-size`
of 18rem keeps it from collapsing inside a parent that sizes to its content, such as a centred grid
or flex column.

## Accessibility

The SVG is `aria-hidden`. Next to it the chart renders the same numbers as a real `<table>`, with
a header row of series names and a row per label. The table is visually hidden but stays in the
accessibility tree, so a screen reader can move through it cell by cell. The caption is `title`,
or `aria_label` when there is no title.

Each point and bar carries an SVG `<title>`, such as `Feb · Visits: 180`, which browsers show as a
native tooltip on hover.

## Theming

Series take colours from `--pjx-chart-1` to `--pjx-chart-8` in order. A ninth series is refused
rather than given a repeated colour, which would read as the same series: fold small series into
an "Other" series or split the chart. The default palette was checked for lightness, chroma,
colour-blind separation and contrast against both a light and a dark surface. Dark mode takes its
own, darker steps of the same eight hues, under `prefers-color-scheme: dark` or
`[data-theme="dark"]` on the root, and `[data-theme="light"]` keeps the light ones.

| Token | Default |
| --- | --- |
| `--pjx-chart-1` … `--pjx-chart-8` | blue, orange, aqua, yellow, magenta, green, violet, red |
| `--pjx-chart-surface` | `var(--surface)`: the ring around each point |
| `--pjx-chart-text` | `var(--text-muted)` |
| `--pjx-chart-title` | `var(--text)` |
| `--pjx-chart-grid` | `var(--border)` at 70% |
| `--pjx-chart-axis` | `var(--border)` |
| `--pjx-chart-font-size` | `12px` |
| `--pjx-chart-line-width` | `2px` |
| `--pjx-chart-area` | `10%`: how strong the wash under a lone line is |
| `--pjx-chart-dim` | `0.3`: the opacity of the other series while one is hovered |

```css
.revenue { --pjx-chart-1: var(--brand); }
```

## What it does not do

The chart has no zoom, pan, crosshair or animated transitions, and there are only two kinds. Each
point is a separate SVG element, so it suits charts of up to a few hundred points per series, not
tens of thousands. Long x labels can still overlap, so keep them short. Value formatting is fixed,
and bars are rounded at both ends, including the one on the zero line.

## DOM contract

- Root `<figure class="pjx-chart pjx-chart--{kind}">`, plus `pjx-chart--dense` on a line chart
  with more than 24 labels. It carries `style="--pjx-chart-height: {height}px"`, and `aria-label`
  only when there is no `title`.
- `<figcaption class="pjx-chart__title">` when `title` is set.
- `<div class="pjx-chart__plot">` holding `<svg class="pjx-chart__svg" aria-hidden="true">`, which
  holds `pjx-chart__grid` lines with a `pjx-chart__y-label` each, the shown `pjx-chart__x-label`s
  (those hidden on a narrow chart also carry `pjx-chart__x-label--minor`) and an optional
  `pjx-chart__zero` line drawn over the marks.
- One `<g class="pjx-chart__series pjx-chart__series--{n}">` per series, `n` from 1 to 8. A line
  series holds a `<svg class="pjx-chart__stretch">` with an optional `pjx-chart__area` path and a
  `pjx-chart__line` path, then a `pjx-chart__point` circle per value. A bar series holds a
  `pjx-chart__bar` rect per value. Each mark contains a `<title>`.
- `<ul class="pjx-chart__legend">` of `pjx-chart__legend-item pjx-chart__series--{n}` items.
- `<div class="pjx-chart__data">` holding the `<table class="pjx-chart__table">`.
- No events, no `data-pjx-*` attributes and no `window.pjx` API.
