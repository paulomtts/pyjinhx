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
