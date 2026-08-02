"""PJXButton — v0.x field/markup parity on the v2 engine.

Port of tests/unit/test_button.py. v0.x's golden snapshots
(tests/unit/golden/button_default.html, button_loading.html) do not carry
over: v2 builtins assert on rendered substrings, like every sibling port.
"""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.ui.pjx_button import PJXButton


class TestFields:
    def test_defaults(self):
        button = PJXButton(id="b")
        assert button.variant == "default"
        assert button.block is False
        assert button.loading is False
        assert button.disabled is False
        assert button.type == "button"
        assert button.class_name == ""
        assert button.content == ""
        assert button.extra_attrs == {}

    def test_content_is_a_declared_slot_field(self):
        assert "content" in PJXButton.__pjx_descriptor__.slot_fields

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXButton(id="b", bogus="x")  # type: ignore[call-arg]

    def test_inline_attr_kwargs_no_longer_pass_through(self):
        """v0.x accepted ``PJXButton(id="b", **{"hx-post": "/save"})``.

        v2 core is strict (extra="forbid"), so a bare inline attr kwarg is now
        a ValidationError — the #500 narrowing. The behavior it replaces is not
        dropped: pass-through moved to the declared ``extra_attrs`` mapping,
        covered by TestRender.test_extra_attrs_surface_on_the_root.
        """
        with pytest.raises(ValidationError):
            PJXButton(id="b", **{"hx-post": "/save"})  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", ["button", "submit", "reset"])
    def test_type_accepts_each_literal(self, value):
        assert PJXButton(id="b", type=value).type == value

    def test_type_rejects_other_values(self):
        with pytest.raises(ValidationError):
            PJXButton(id="b", type="link")  # type: ignore[arg-type]
