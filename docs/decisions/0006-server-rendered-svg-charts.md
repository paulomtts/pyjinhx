# ADR 0006: Charts are SVG drawn on the server, with no JavaScript

**Status:** Accepted, 2026-11-11. Unreleased.

## Context

pyjinhx had no way to show data charts. `PJXGraph` draws node graphs (boxes and
wires on a pan/zoom canvas, see [ADR 0004](0004-graph-reconcile-model.md)), not
line or bar charts of numbers.

An app wants a chart for a dashboard tile or a report: a few series over a few
dozen labels, refreshed by an htmx poll or swapped in with the rest of a page.
That raised one question: draw the chart in the browser with a JavaScript
library, or in Python as markup.

The candidates were measured from their npm packages on 2026-11-11:

| Option | Licence | Runtime deps | Minified | Gzipped | Renders without JS |
| --- | --- | --- | --- | --- | --- |
| Server-side SVG in Python | the library's own | none | 0 (about 3 KB of CSS) | — | yes |
| uPlot 1.6.32 | MIT | none | 51 KB | 22 KB | no (canvas) |
| d3-scale 4 + d3-shape 3 + d3-axis 3 | ISC | 7 more d3 modules | 53 KB | 17 KB | no |
| Chart.js 4.6.1 | MIT | `@kurkle/color` | 210 KB | 71 KB | no (canvas) |
| ECharts 6.1.0 | Apache-2.0 | `zrender`, `tslib` | 1,122 KB (500 KB "simple") | 368 KB | only through Node |

## Decision: draw the chart in Python as SVG

`PJXChart` works out the scale, ticks and mark positions in a pydantic validator
and its template writes them out as an `<svg>`. The data is a list of
`PJXChartSeries`, a frozen model with a `name` and one value per label, which
follows `PJXRosterItem` and `SelectOption`. There are two kinds, `line` and
`bar`.

This fits how pyjinhx already works:

- **htmx swaps need nothing.** A chart is markup, so `outerHTML`, OOB swaps and
  `hx-trigger="every 30s"` replace it like any other element. A JavaScript chart
  needs a mount on `htmx:load` and a teardown when a swap removes it, or a
  replaced chart leaks its instance. That is the lifecycle ADR 0004 had to
  solve for the graph.
- **First paint and no-JS.** The chart is in the server's HTML, so it shows
  before any script runs, prints, and works with scripts off.
- **Escaping is the template's.** Labels and series names go through Jinja's
  autoescape like every other prop. A JavaScript library would take them as
  data from a JSON island, which is a second escaping path to get right.
- **Tested in Python.** The geometry is plain arithmetic in one module, checked
  by render tests. Chromium tests cover only the stylesheet and the swap.
- **Nothing to vendor.** There is no pin, licence header, size budget or build
  step to keep, unlike `scripts/vendor_d3_zoom.py`.
- **Sharp at any size.** SVG is vector, so it is crisp at any zoom or pixel
  density, which canvas only matches when the library handles the device
  pixel ratio. Marks are placed in percentages of the plot and lines opt out
  of scaling, so text and strokes keep their pixel size at any width.
- **Accessible by default.** The SVG is `aria-hidden` and a visually hidden
  `<table>` carries the same numbers. Each mark has a `<title>` that browsers
  show as a tooltip.

## Decision: the chart is laid out in percentages, not a scaled viewBox

A first version drew into a fixed viewBox that scaled with the container. Its
text and lines shrank with the chart, so a chart in a narrow card had tiny
labels and hairline strokes. Now each position is a percentage of the plot,
the axis labels sit in CSS gutters, and the chart takes a pixel `height`.
Only a line path, which cannot use percentages, is drawn in a viewBox
stretched to the plot, with `vector-effect: non-scaling-stroke`.

The x labels are thinned on the server to at most twelve, and a container
query hides every other one on a chart narrower than 30rem. That needs the
chart to be a size container, so it sets `contain-intrinsic-inline-size`, or
it would collapse to no width inside a parent that sizes to its content.

## Rejected: uPlot

uPlot is the smallest and fastest JavaScript option and has no dependencies,
and the one to pick if the builtin ever needs crosshairs and zoom. It draws on
canvas, so it shows nothing before its script runs and nothing to a screen
reader. It also needs the mount and teardown described above. Its speed pays
off for tens of thousands of points, which is not the chart this builtin is
for.

## Rejected: building on d3

The graph's vendored d3 has no scales, shapes or axes. Adding d3-scale,
d3-shape and d3-axis costs about 53 KB minified. d3-axis also renders through
d3-selection, and the graph's copy of it is inside that builtin's private IIFE,
so the chart would ship a second copy. d3 also leaves the layout and drawing to
the caller, so we would still write a chart engine, only in JavaScript, and add
the mount lifecycle on top.

## Rejected: Chart.js

Chart.js has many chart types and good defaults, but it is four times uPlot's
size, draws on canvas and has the same lifecycle cost. Its configuration object
is a large API of its own, and the builtin would either wrap it, which is a lot
of surface, or pass it through, which is not a pyjinhx API.

## Rejected: ECharts

ECharts is the most capable option and has server-side SVG rendering, but only
in Node. A Python server would have to call Node or ship about 370 KB gzipped to
every page. Neither fits a library whose promise is server-rendered HTML.

## Consequences

- No JavaScript ships with charts, so there are no `pjx:chart:*` events and no
  `window.pjx` entry. Interaction is limited to native SVG tooltips and CSS
  hover.
- No zoom, pan, crosshair or animation. If an app needs them, a JavaScript
  chart in a classless component of its own is the escape hatch. A future
  interactive builtin would need its own ADR.
- Each point and bar is an element, so the markup grows with the data. Up to a
  few hundred points per series is fine; tens of thousands is the case uPlot
  exists for.
- The tick and layout code is ours to maintain: about 200 lines of Python in
  `pyjinhx/builtins/ui/pjx_chart/pjx_chart.py`.
- At most eight series, one per palette colour. A ninth is refused rather than
  given a repeated colour.
- Bars are rounded at both ends. Squaring the end on the zero line needs a
  clip path per chart and is left for later.
- More kinds (area, stacked bars) and value formatting are left for later.
  They fit the same model: more geometry in the validator, more markup in the
  template.

## Related

- [Chart guide](../guide/chart.md): the props, the scale rules, accessibility
  and theming.
- [Builtin conventions](../guide/builtin-conventions.md): the contract every
  builtin follows.
- [ADR 0004](0004-graph-reconcile-model.md): the mount lifecycle a JavaScript
  builtin carries, which this one avoids.
