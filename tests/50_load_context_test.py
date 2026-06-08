from dataclasses import dataclass
from typing import ClassVar

from pyjinhx import LoadCache, ReactiveComponent, Registry
from pyjinhx.reactive.context import LoadContext


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
        ctx = LoadContext.current()
        value = ctx.value if isinstance(ctx, AppLoadContext) else -1
        return cls(id="ctx-plain", value=value)


def test_load_context_current_outside_scope_is_none():
    assert LoadContext.current() is None


def test_load_context_bind_sets_context():
    ctx = AppLoadContext(value=7)
    with LoadContext.bind(ctx):
        assert LoadContext.current() is ctx
    assert LoadContext.current() is None


def test_load_receives_ctx_kwarg():
    LoadCache.clear()
    ctx = AppLoadContext(value=42)
    with LoadContext.bind(ctx):
        instance = CtxSingleton.load()
    assert instance.value == 42


def test_keyed_load_with_ctx_kwarg_stays_keyed():
    assert CtxKeyed._pjx_keyed is True
    LoadCache.clear()
    ctx = AppLoadContext(value=9)
    with LoadContext.bind(ctx):
        row = CtxKeyed.load("a")
    assert row.label == "a:9"
    assert row.id == "ctx-keyed-a"


def test_load_contextvar_when_no_ctx_param():
    LoadCache.clear()
    ctx = AppLoadContext(value=5)
    with LoadContext.bind(ctx):
        instance = CtxPlain.load()
    assert instance.value == 5


def test_request_scope_accepts_load_context():
    LoadCache.clear()
    ctx = AppLoadContext(value=11)
    with Registry.request_scope(load_context=ctx):
        instance = CtxPlain.load()
    assert instance.value == 11


def test_load_context_accepts_ctx_detects_keyword_only():
    def with_ctx(cls, *, ctx=None):
        pass

    def without_ctx(cls):
        pass

    assert LoadContext.accepts_ctx(with_ctx) is True
    assert LoadContext.accepts_ctx(without_ctx) is False
