"""PJXSegmentedControl — v0.x field/markup parity on the v2 engine.

Partial port of tests/unit/test_toggle_segmented.py: only the
``test_segmented_control_*`` cases carry over here. The PJXToggleSwitch cases in
that same file belong to #514. v0.x's golden-snapshot comparison does not carry
over either — v2 builtins assert on rendered substrings, like every sibling
port.
"""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.ui.pjx_segmented_control import PJXSegmentedControl


class TestFields:
    def test_defaults(self):
        control = PJXSegmentedControl(id="sc", name="plan")
        assert control.name == "plan"
        assert control.options == []
        assert control.selected == ""
        assert control.disabled is False
        assert control.class_name == ""
        assert control.extra_attrs == {}

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXSegmentedControl(id="sc", name="plan", bogus="x")  # type: ignore[call-arg]

    def test_inline_attr_kwargs_no_longer_pass_through(self):
        """v0.x accepted ``PJXSegmentedControl(..., **{"data-test": "1"})``.

        v2 core is strict (extra="forbid"), so a bare inline attr kwarg is now a
        ValidationError. The behavior it replaces is not dropped: pass-through
        moved to the declared ``extra_attrs`` mapping, covered by
        TestRender.test_extra_attrs_surface_on_the_root.
        """
        with pytest.raises(ValidationError):
            PJXSegmentedControl(id="sc", name="plan", **{"data-test": "1"})  # type: ignore[arg-type]

    def test_json_string_options_coercion(self):
        control = PJXSegmentedControl(
            id="sc", name="plan", options='[["a","A"],["b","B"]]'
        )
        assert control.options == [("a", "A"), ("b", "B")]
