import math
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from pyjinhx._component import AttrValue, BaseComponent, ExtraAttrs
from pyjinhx.builtins.ui.pjx_chart.series import FiniteFloat, PJXChartSeries

# One --pjx-chart-<n> colour token per series. A ninth series would need a
# repeated or generated hue, which reads as the same series, so it is refused.
PALETTE_SIZE = 8
# Past this many labels the points crowd the line, so they show only on hover.
DENSE_LABELS = 24
# Shares of a label's band: what a bar group fills (a lone bar gets less, or
# it reads as a block), and what each bar fills of its slot in the group.
GROUP_SHARE = 0.7
LONE_SHARE = 0.5
BAR_SHARE = 0.85
# Most x labels a chart shows; a narrow chart shows half of them.
MAX_X_LABELS = 12


def _nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    """About ``count`` evenly spaced round values that cover ``low`` to ``high``."""
    if low == high:
        low, high = (0, 1) if low == 0 else (low - 1, high + 1)
    raw = (high - low) / count
    power = 10 ** math.floor(math.log10(raw))
    # d3's thresholds: pick the 1, 2, 5 or 10 multiple nearest the raw step.
    ratio = raw / power
    step = power * (
        10 if ratio >= 7.07 else 5 if ratio >= 3.16 else 2 if ratio >= 1.41 else 1
    )
    start = math.floor(low / step)
    stop = math.ceil(high / step)
    return [round(i * step, 10) for i in range(start, stop + 1)]


def _format_value(value: float) -> str:
    """A value in full: thousands separated, float noise dropped."""
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.6g}"


def _compact(value: float) -> str:
    """A value shortened with K, M or B, for axis ticks that reach 10,000."""
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= size:
            return f"{value / size:.3g}{suffix}"
    return _format_value(value)


def _pct(value: float) -> float:
    return round(value * 100, 2)


class PJXChart(BaseComponent):
    """A line or bar chart drawn on the server as SVG, with no JavaScript.

    Each series has one value per label; a ``None`` value breaks the line or
    leaves out the bar. The y axis gets round ticks that cover the data, and
    a bar chart's always includes zero. ``y_min`` and ``y_max`` fix either end
    instead, and marks past them are clamped to the plot's edge.

    The chart fills its container's width at ``height`` pixels. Marks are
    placed in percentages of the plot, so text and strokes keep their pixel
    size at any width. The SVG is hidden from assistive technology; a
    visually hidden table holds the same data. ``title`` is the visible
    caption, else ``aria_label`` names the chart.
    """

    labels: list[str] = Field(min_length=1)
    series: list[PJXChartSeries] = Field(min_length=1, max_length=PALETTE_SIZE)
    kind: Literal["line", "bar"] = "line"
    title: str = ""
    aria_label: str = "Chart"
    legend: bool = True
    y_min: FiniteFloat | None = None
    y_max: FiniteFloat | None = None
    height: int = Field(default=240, ge=80)
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    # Derived from the data, not user-supplied: the geometry is worked out
    # here so the template only places what it is given. Every position is a
    # percentage of the plot, y measured down from its top.
    y_ticks: list[dict[str, Any]] = Field(default_factory=list)
    x_ticks: list[dict[str, Any]] = Field(default_factory=list)
    zero_y: float | None = None
    dense: bool = False
    marks: list[dict[str, Any]] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _lay_out(self) -> Self:
        for series in self.series:
            if len(series.values) != len(self.labels):
                raise ValueError(
                    f"{series.name} has {len(series.values)} values"
                    f" for {len(self.labels)} labels"
                )
        if (
            self.y_min is not None
            and self.y_max is not None
            and self.y_min >= self.y_max
        ):
            raise ValueError("y_min must be below y_max")

        values = [v for s in self.series for v in s.values if v is not None]
        if self.kind == "bar":
            values.append(0)
        low = self.y_min if self.y_min is not None else min(values, default=0)
        high = self.y_max if self.y_max is not None else max(values, default=0)
        # A fixed end can lie past all the data; the axis then starts from it.
        if self.y_min is not None:
            high = max(high, low)
        if self.y_max is not None:
            low = min(low, high)
        ticks = _nice_ticks(low, high)
        bottom = self.y_min if self.y_min is not None else ticks[0]
        top = self.y_max if self.y_max is not None else ticks[-1]
        band = 1 / len(self.labels)

        def y_of(value: float) -> float:
            value = min(max(value, bottom), top)
            return _pct((top - value) / (top - bottom))

        def center(index: int) -> float:
            return _pct(band * (index + 0.5))

        ticks = [t for t in ticks if bottom <= t <= top]
        label = _compact if max(abs(t) for t in ticks) >= 10_000 else _format_value
        self.y_ticks = [{"y": y_of(t), "text": label(t)} for t in ticks]
        # Thinned to fit, keeping the first: the stylesheet hides the minor
        # ones on a narrow chart. Tooltips and the table still name every label.
        stride = math.ceil(len(self.labels) / MAX_X_LABELS)
        narrow = stride * 2 if len(self.labels) > MAX_X_LABELS / 2 else 1
        self.x_ticks = [
            {"x": center(i), "text": text, "minor": i % narrow != 0}
            for i, text in enumerate(self.labels)
            if i % stride == 0
        ]
        self.zero_y = y_of(0) if bottom <= 0 <= top else None
        self.dense = self.kind == "line" and len(self.labels) > DENSE_LABELS
        base = self.zero_y if self.zero_y is not None else 100.0

        group = GROUP_SHARE if len(self.series) > 1 else LONE_SHARE
        slot = band * group / len(self.series)
        self.marks = []
        for n, series in enumerate(self.series):
            points = []
            runs: list[list[tuple[float, float]]] = []
            for i, value in enumerate(series.values):
                if value is None:
                    continue
                tip = f"{self.labels[i]} · {series.name}: {_format_value(value)}"
                y = y_of(value)
                if self.kind == "bar":
                    zero = y_of(0)
                    left = band * (i + (1 - group) / 2) + slot * n
                    points.append(
                        {
                            "x": _pct(left + slot * (1 - BAR_SHARE) / 2),
                            "y": min(y, zero),
                            "width": _pct(slot * BAR_SHARE),
                            "height": round(abs(zero - y), 2),
                            "tip": tip,
                        }
                    )
                else:
                    if i == 0 or series.values[i - 1] is None:
                        runs.append([])
                    runs[-1].append((center(i), y))
                    points.append({"x": center(i), "y": y, "tip": tip})
            line = " ".join(
                " ".join(
                    f"{'M' if k == 0 else 'L'}{x} {y}" for k, (x, y) in enumerate(run)
                )
                for run in runs
            )
            # A wash under the line helps one series read as a shape; under
            # several, the washes overlap into mud.
            area = ""
            if len(self.series) == 1:
                area = " ".join(
                    f"M{run[0][0]} {base} "
                    + " ".join(f"L{x} {y}" for x, y in run)
                    + f" L{run[-1][0]} {base} Z"
                    for run in runs
                )
            self.marks.append(
                {
                    "name": series.name,
                    "color": n + 1,
                    "line": line,
                    "area": area,
                    "points": points,
                }
            )

        columns = zip(*(s.values for s in self.series))
        self.rows = [
            {
                "label": text,
                "cells": ["" if v is None else _format_value(v) for v in row],
            }
            for text, row in zip(self.labels, columns)
        ]
        return self
