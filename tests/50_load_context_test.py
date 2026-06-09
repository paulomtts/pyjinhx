from dataclasses import dataclass
from typing import Annotated, ClassVar

import pytest

from pyjinhx import LoadCache, PjxLoad, ReactiveComponent, Registry
from pyjinhx.context import (
    LoadContext,
    resolve_load_context_param,
)


@dataclass(frozen=True)
class AppLoadContext(LoadContext):
    value: int = 0


class CtxSingleton(ReactiveComponent):
    value: int = 0
    reacts_to: ClassVar[set[str]] = {"widgets"}

    @classmethod
    def load(cls, *, app: AppLoadContext | None = None) -> "CtxSingleton":
        return cls(id="ctx-singleton", value=app.value if app else -1)


class CtxKeyed(ReactiveComponent):
    row_key: Annotated[str, PjxLoad()]
    label: str = ""
    reacts_to: ClassVar[set[str]] = {"row"}

    @classmethod
    def load(cls, key: str, app_ctx: AppLoadContext) -> "CtxKeyed":
        return cls(row_key=key, label=f"{key}:{app_ctx.value}")


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


def test_load_receives_context_by_type_not_name():
    LoadCache.clear()
    ctx = AppLoadContext(value=42)
    with LoadContext.bind(ctx):
        instance = CtxSingleton.load()
    assert instance.value == 42


def test_keyed_load_injects_context_positionally():
    assert CtxKeyed._pjx_keyed is True
    LoadCache.clear()
    ctx = AppLoadContext(value=9)
    with LoadContext.bind(ctx):
        row = CtxKeyed.load("a")
    assert row.label == "a:9"
    assert row.id == "ctx-keyed-a"


def test_load_contextvar_when_no_context_param():
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


def test_resolve_load_context_param_detects_subclass_annotation():
    def with_context(cls, *, app: AppLoadContext | None = None):
        pass

    def without_context(cls):
        pass

    assert resolve_load_context_param(with_context).name == "app"
    assert resolve_load_context_param(without_context) is None


def test_duplicate_load_context_params_raise_at_class_definition():
    with pytest.raises(TypeError, match="multiple LoadContext parameters"):

        class DuplicateCtxLoad(ReactiveComponent):
            reacts_to: ClassVar[set[str]] = {"dup"}

            @classmethod
            def load(
                cls,
                first: AppLoadContext,
                second: LoadContext,
            ) -> "DuplicateCtxLoad":
                return cls(id="dup")
