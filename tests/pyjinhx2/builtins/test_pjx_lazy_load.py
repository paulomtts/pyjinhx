"""PJXLazyLoad — v0.x field/markup parity on the v2 engine."""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.pjx_lazy_load import PJXLazyLoad


class TestFields:
    def test_defaults(self):
        lazy = PJXLazyLoad(id="lz", url="/x")
        assert lazy.when == "viewport"
        assert lazy.trigger == ""
        assert lazy.swap == "outerHTML"
        assert lazy.tag == "div"
        assert lazy.content == ""
        assert lazy.error == ""
        assert lazy.error_text == "Failed to load."
        assert lazy.class_name == ""
        assert lazy.extra_attrs == {}


class TestValidation:
    def test_url_is_required(self):
        with pytest.raises(ValidationError):
            PJXLazyLoad(id="lz")  # type: ignore[call-arg]

    def test_invalid_when_raises(self):
        with pytest.raises(ValidationError):
            PJXLazyLoad(id="lz", url="/x", when="hover")  # type: ignore[arg-type]

    def test_invalid_tag_raises(self):
        with pytest.raises(ValidationError):
            PJXLazyLoad(id="lz", url="/x", tag="span")  # type: ignore[arg-type]

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXLazyLoad(id="lz", url="/x", bogus="x")  # type: ignore[call-arg]
