"""The y-axis scale: nice tick steps and the value text axes and tooltips show."""

import pytest

from pyjinhx.builtins.ui.pjx_chart.pjx_chart import _compact, _format_value, _nice_ticks


@pytest.mark.parametrize(
    ("low", "high", "want"),
    [
        (0, 10, [0, 2, 4, 6, 8, 10]),
        (0, 9.3, [0, 2, 4, 6, 8, 10]),
        (3, 97, [0, 20, 40, 60, 80, 100]),
        (-12, 30, [-20, -10, 0, 10, 20, 30]),
        (0, 0.43, [0, 0.1, 0.2, 0.3, 0.4, 0.5]),
        (1200, 1260, [1200, 1210, 1220, 1230, 1240, 1250, 1260]),
    ],
)
def test_ticks_cover_the_range_on_round_steps(low, high, want):
    assert _nice_ticks(low, high) == want


def test_a_flat_range_still_gets_an_axis():
    assert _nice_ticks(5, 5) == [4, 4.5, 5, 5.5, 6]
    assert _nice_ticks(0, 0) == [0, 0.2, 0.4, 0.6, 0.8, 1]


@pytest.mark.parametrize(
    ("value", "want"),
    [
        (0, "0"),
        (12.0, "12"),
        (1234567, "1,234,567"),
        (0.30000000000000004, "0.3"),
        (-2.5, "-2.5"),
    ],
)
def test_values_read_as_plain_numbers(value, want):
    assert _format_value(value) == want


@pytest.mark.parametrize(
    ("value", "want"),
    [
        (0, "0"),
        (5000, "5K"),
        (12500, "12.5K"),
        (-250000, "-250K"),
        (2_000_000, "2M"),
        (3e9, "3B"),
    ],
)
def test_compact_values_use_k_m_b(value, want):
    assert _compact(value) == want
