from dataclasses import dataclass

import pytest

from pyjinhx import BaseComponent, MutationKey, ReactiveComponent
from pyjinhx.cache import LoadCache
from pyjinhx.context import PjxContext


@dataclass(frozen=True)
class Ctx(PjxContext):
    value: int = 0


class CtxWidget(BaseComponent):
    def describe(self, ctx: Ctx | None = None) -> str:
        return f"v={ctx.value}" if ctx else "none"

    @classmethod
    def from_ctx(cls, ctx: Ctx | None = None) -> str:
        return f"cls:{ctx.value}" if ctx else "cls:none"

    @staticmethod
    def stat(ctx: Ctx | None = None) -> str:
        return f"stat:{ctx.value}" if ctx else "stat:none"

    def greet(self, name: str, ctx: Ctx | None = None) -> str:
        return f"{name}:{ctx.value if ctx else '-'}"

    def plain(self, x: int) -> int:
        return x * 2


def test_instance_method_injected_inside_scope():
    widget = CtxWidget()
    with PjxContext.bind(Ctx(value=5)):
        assert widget.describe() == "v=5"


def test_instance_method_none_outside_scope():
    widget = CtxWidget()
    assert widget.describe() == "none"


def test_classmethod_injected():
    with PjxContext.bind(Ctx(value=7)):
        assert CtxWidget.from_ctx() == "cls:7"


def test_staticmethod_injected():
    with PjxContext.bind(Ctx(value=9)):
        assert CtxWidget.stat() == "stat:9"


def test_classmethod_none_outside_scope():
    assert CtxWidget.from_ctx() == "cls:none"


def test_staticmethod_none_outside_scope():
    assert CtxWidget.stat() == "stat:none"


def test_explicit_positional_arg_respected():
    widget = CtxWidget()
    with PjxContext.bind(Ctx(value=5)):
        assert widget.describe(Ctx(value=99)) == "v=99"


def test_explicit_keyword_arg_respected():
    widget = CtxWidget()
    with PjxContext.bind(Ctx(value=5)):
        assert widget.describe(ctx=Ctx(value=42)) == "v=42"


def test_other_positional_args_plus_injection():
    widget = CtxWidget()
    with PjxContext.bind(Ctx(value=8)):
        assert widget.greet("hi") == "hi:8"


def test_method_without_ctx_param_not_wrapped():
    widget = CtxWidget()
    assert widget.plain(3) == 6
    assert getattr(vars(CtxWidget)["plain"], "_pjx_ctx_injected", False) is False


def test_multiple_ctx_params_raise_at_class_definition():
    with pytest.raises(TypeError):

        class BadMultiCtx(BaseComponent):
            def m(self, a: Ctx, b: Ctx | None = None) -> None:
                ...
