"""PJXSelect multi-select mode (#866) — checkboxes, chip trigger summary, native multi.

Single-select behaviour lives in test_pjx_select.py. Search (#867), keyboard nav
(#868) and the exhaustive cross-cutting suite (#869) are separate subtasks;
nothing here anticipates their markup.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_select import PJXSelect, SelectOption
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

OPTIONS = [
    SelectOption(value="a", label="Apple"),
    SelectOption(value="b", label="Banana"),
    SelectOption(value="c", label="Cherry"),
]


class TestMultipleFields:
    def test_multiple_defaults_to_false(self):
        assert PJXSelect(id="s", name="fruit", options=OPTIONS).multiple is False

    def test_multi_mode_accepts_a_list_value(self):
        sel = PJXSelect(
            id="s", name="fruit", options=OPTIONS, multiple=True, value=["a", "b"]
        )
        assert sel.value == ["a", "b"]

    def test_multi_mode_accepts_none(self):
        sel = PJXSelect(id="s", name="fruit", options=OPTIONS, multiple=True)
        assert sel.value is None

    def test_multiple_value_type_mismatch_raises(self):
        with pytest.raises(ValidationError):
            PJXSelect(id="s", name="fruit", options=OPTIONS, multiple=True, value="a")
        with pytest.raises(ValidationError):
            PJXSelect(id="s", name="fruit", options=OPTIONS, value=["a"])
