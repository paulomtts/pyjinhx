"""AppContext: the injectable-context marker and the once-per-class resolver."""

from __future__ import annotations

from typing import Any

import pytest

from pyjinhx.app_context import AppContext, resolve_load_context_param


class MyAppContext(AppContext):
    """An app-defined context, the shape a real app's context_factory returns."""

    def __init__(self, user: str = "") -> None:
        self.user = user


class OtherContext(AppContext):
    """A second app context class, for the two-params error case."""


def test_zero_arg_load_resolves_to_none():
    def load(self: Any) -> None:
        return None

    assert resolve_load_context_param(load) is None


def test_annotated_param_resolves_to_its_name():
    def load(self: Any, ctx: MyAppContext) -> None:
        return None

    assert resolve_load_context_param(load) == "ctx"


def test_resolution_is_by_annotation_not_by_parameter_name():
    def load(self: Any, whatever: MyAppContext) -> None:
        return None

    assert resolve_load_context_param(load) == "whatever"


def test_a_param_named_ctx_without_the_annotation_does_not_resolve():
    def load(self: Any, ctx: str = "") -> None:
        return None

    assert resolve_load_context_param(load) is None


def test_optional_union_annotation_resolves():
    def load(self: Any, ctx: MyAppContext | None) -> None:
        return None

    assert resolve_load_context_param(load) == "ctx"


def test_the_marker_base_itself_resolves():
    def load(self: Any, ctx: AppContext) -> None:
        return None

    assert resolve_load_context_param(load) == "ctx"


def test_unresolvable_annotation_is_treated_as_a_non_match():
    # `from __future__ import annotations` is required *inside* the exec'd
    # source: without it the bare `def` evaluates `NoSuchContextClass`
    # immediately and this exec() call itself raises NameError, before
    # resolve_load_context_param ever runs. With it, the annotation is a
    # string and evaluation is deferred to get_type_hints() inside the
    # resolver -- which is the forward-ref case this test means to cover.
    namespace: dict[str, Any] = {}
    exec(  # noqa: S102 -- the string annotation is the point of the test
        "from __future__ import annotations\n"
        "def load(self, ctx: NoSuchContextClass): ...",
        namespace,
    )

    assert resolve_load_context_param(namespace["load"]) is None


def test_two_context_params_raise_at_resolution_time():
    def load(self: Any, first: MyAppContext, second: OtherContext) -> None:
        return None

    with pytest.raises(TypeError, match="at most one"):
        resolve_load_context_param(load)
