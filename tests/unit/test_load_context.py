from dataclasses import dataclass
from typing import Annotated

import pytest

from pyjinhx import MutationKey, PjxKey, ReactiveComponent, Registry
from pyjinhx.cache import LoadCache
from pyjinhx.context import (
    PjxContext,
    resolve_load_context_param,
)


class Keys(MutationKey):
    WIDGETS = "widgets"
    ROW = "row"
    PLAIN = "plain"
    DUP = "dup"


@dataclass(frozen=True)
class AppLoadContext(PjxContext):
    value: int = 0


class CtxSingleton(ReactiveComponent, react={Keys.WIDGETS}):
    value: int = 0

    @classmethod
    def load(cls, *, app: AppLoadContext | None = None) -> "CtxSingleton":
        return cls(id="ctx-singleton", value=app.value if app else -1)


class CtxKeyed(ReactiveComponent, react={Keys.ROW}):
    row_key: Annotated[str, PjxKey()]
    label: str = ""

    @classmethod
    def load(cls, key: str, app_ctx: AppLoadContext) -> "CtxKeyed":
        return cls(row_key=key, label=f"{key}:{app_ctx.value}")


class CtxPlain(ReactiveComponent, react={Keys.PLAIN}):
    value: int = 0

    @classmethod
    def load(cls) -> "CtxPlain":
        ctx = PjxContext.current()
        value = ctx.value if isinstance(ctx, AppLoadContext) else -1
        return cls(id="ctx-plain", value=value)


def test_load_context_current_outside_scope_is_none():
    assert PjxContext.current() is None


def test_load_context_bind_sets_context():
    ctx = AppLoadContext(value=7)
    with PjxContext.bind(ctx):
        assert PjxContext.current() is ctx
    assert PjxContext.current() is None


def test_load_receives_context_by_type_not_name():
    LoadCache.clear()
    ctx = AppLoadContext(value=42)
    with PjxContext.bind(ctx):
        instance = CtxSingleton.load()
    assert instance.value == 42


def test_keyed_load_injects_context_positionally():
    assert CtxKeyed._pjx_keyed is True
    LoadCache.clear()
    ctx = AppLoadContext(value=9)
    with PjxContext.bind(ctx):
        row = CtxKeyed.load("a")  # type: ignore[call-arg]  # app_ctx injected from PjxContext
    assert row.label == "a:9"
    assert row.id == "ctx-keyed-a"


def test_load_contextvar_when_no_context_param():
    LoadCache.clear()
    ctx = AppLoadContext(value=5)
    with PjxContext.bind(ctx):
        instance = CtxPlain.load()
    assert instance.value == 5


def test_request_scope_accepts_load_context():
    LoadCache.clear()
    ctx = AppLoadContext(value=11)
    with Registry.request_scope(load_context=ctx):
        instance = CtxPlain.load()
    assert instance.value == 11


def test_resolve_load_context_param_detects_subclass_annotation():
    def with_context(cls, *, app: AppLoadContext | None = None):
        pass

    def without_context(cls):
        pass

    resolved = resolve_load_context_param(with_context)
    assert resolved is not None and resolved.name == "app"
    assert resolve_load_context_param(without_context) is None


def test_duplicate_load_context_params_raise_at_class_definition():
    with pytest.raises(TypeError, match="multiple PjxContext parameters"):

        class DuplicateCtxLoad(ReactiveComponent, react={Keys.DUP}):
            @classmethod
            def load(
                cls,
                first: AppLoadContext,
                second: PjxContext,
            ) -> "DuplicateCtxLoad":
                return cls(id="dup")
