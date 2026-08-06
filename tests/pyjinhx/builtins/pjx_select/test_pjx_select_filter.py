"""PJXSelect — the option-list filter input.

The filter is presentation-only: it hides option buttons in the browser and
never touches the native <select> or any selection state. Keyboard nav (#868)
and the exhaustive cross-cutting suite (#869) are separate subtasks.
"""

import pytest

from pyjinhx.builtins.ui.pjx_select import PJXSelect, SelectOption
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

FRUITS = [
    "Apple",
    "Banana",
    "Cherry",
    "Date",
    "Elderberry",
    "Fig",
    "Grape",
    "Honeydew",
    "Iceberg",
    "Jackfruit",
]


def options(count: int) -> list[SelectOption]:
    """First ``count`` fruit options, value "o0", "o1", ... in order."""
    return [
        SelectOption(value=f"o{i}", label=FRUITS[i]) for i in range(count)
    ]


class TestFields:
    def test_filter_threshold_default(self):
        assert PJXSelect._FILTER_THRESHOLD == 8
