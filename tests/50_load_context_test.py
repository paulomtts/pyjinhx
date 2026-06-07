from dataclasses import dataclass
from typing import ClassVar

from pyjinhx import ReactiveComponent, Registry
from pyjinhx.cache import clear
from pyjinhx.load_context import LoadContext, get_load_context, load_scope


@dataclass(frozen=True)
class AppLoadContext(LoadContext):
    value: int = 0


class CtxSingleton(ReactiveComponent):
    value: int = 0
    reacts_to: ClassVar[set[str]] = {"widgets"}

    @classmethod
    def load(cls, *, ctx: AppLoadContext | None = None) -> "CtxSingleton":
        return cls(id="ctx-singleton", value=ctx.value if ctx else -1)


class CtxKeyed(ReactiveComponent):
    label: str = ""
    reacts_to: ClassVar[set[str]] = {"row"}

    @classmethod
    def load(cls, key: str, *, ctx: AppLoadContext | None = None) -> "CtxKeyed":
        return cls(label=f"{key}:{ctx.value if ctx else 'none'}")


class CtxPlain(ReactiveComponent):
    value: int = 0
    reacts_to: ClassVar[set[str]] = {"plain"}

    @classmethod
    def load(cls) -> "CtxPlain":
        ctx = get_load_context()
        value = ctx.value if isinstance(ctx, AppLoadContext) else -1
        return cls(id="ctx-plain", value=value)


def test_get_load_context_outside_scope_is_none():
    assert get_load_context() is None


def test_load_scope_sets_context():
    ctx = AppLoadContext(value=7)
    with load_scope(ctx):
        assert get_load_context() is ctx
    assert get_load_context() is None


def test_load_receives_ctx_kwarg():
    clear()
    ctx = AppLoadContext(value=42)
    with load_scope(ctx):
        instance = CtxSingleton.load()
    assert instance.value == 42


def test_keyed_load_with_ctx_kwarg_stays_keyed():
    assert CtxKeyed._pjx_keyed is True
    clear()
    ctx = AppLoadContext(value=9)
    with load_scope(ctx):
        row = CtxKeyed.load("a")
    assert row.label == "a:9"
    assert row.id == "ctx-keyed-a"


def test_load_reads_contextvar_when_no_ctx_param():
    clear()
    ctx = AppLoadContext(value=5)
    with load_scope(ctx):
        instance = CtxPlain.load()
    assert instance.value == 5


def test_request_scope_accepts_load_context():
    clear()
    ctx = AppLoadContext(value=11)
    with Registry.request_scope(load_context=ctx):
        instance = CtxPlain.load()
    assert instance.value == 11
