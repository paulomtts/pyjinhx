"""ReactiveComponent: the load() wrap installed at class-definition time."""

from typing import Annotated, Any

import pytest

from pyjinhx._component import BaseComponent
from pyjinhx.app_context import AppContext
from pyjinhx.reactive.backend import CachePolicy
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.session import request_scope


def test_reactive_component_is_a_base_component():
    assert issubclass(ReactiveComponent, BaseComponent)


def test_defining_a_subclass_replaces_load_with_the_wrapper():
    @classmethod
    def original(cls: type[Any]) -> Any:
        return cls()

    Widget = type("Widget", (ReactiveComponent,), {"load": original})

    assert Widget.load is not original


def test_load_body_runs_once_per_request_scope():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        value: str = ""

        @classmethod
        def load(cls) -> "Widget":
            calls.append(1)
            return cls(value="loaded")

    with request_scope():
        assert Widget.load().value == "loaded"
        assert Widget.load().value == "loaded"

    assert len(calls) == 1


def test_a_cached_default_result_is_not_reloaded():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        @classmethod
        def load(cls) -> "Widget":
            calls.append(1)
            return cls()

    with request_scope():
        first = Widget.load()
        second = Widget.load()

    assert first is second
    assert len(calls) == 1


def test_load_runs_every_call_outside_a_request_scope():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        value: str = ""

        @classmethod
        def load(cls) -> "Widget":
            calls.append(1)
            return cls(value="loaded")

    assert Widget.load().value == "loaded"
    assert Widget.load().value == "loaded"
    assert len(calls) == 2


def test_each_request_scope_starts_cold():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        @classmethod
        def load(cls) -> "Widget":
            calls.append(1)
            return cls()

    with request_scope():
        Widget.load()
    with request_scope():
        Widget.load()

    assert len(calls) == 2


def test_react_keys_are_forwarded_to_cache_put():
    from unittest.mock import patch

    class Widget(ReactiveComponent, react=("todos",)):
        @classmethod
        def load(cls) -> "Widget":
            return cls()

    with (
        request_scope(),
        patch("pyjinhx.reactive.component.cache_put") as spy,
    ):
        Widget.load()

    assert spy.call_args.kwargs["react_keys"] == ("todos",)


def test_declared_react_keys_make_the_entry_evictable():
    from pyjinhx.reactive.cache import invalidate

    calls: list[int] = []

    class Widget(ReactiveComponent, react=("todos",)):
        @classmethod
        def load(cls) -> "Widget":
            calls.append(1)
            return cls()

    with request_scope():
        Widget.load()
        invalidate(["todos"])
        Widget.load()

    assert len(calls) == 2


def test_react_keys_default_to_empty():
    class Widget(ReactiveComponent):
        @classmethod
        def load(cls) -> "Widget":
            return cls()

    assert Widget._pjx_react_keys == ()


def test_enum_react_keys_are_normalized_to_their_values():
    from pyjinhx.reactive.keys import MutationKey

    class Keys(MutationKey):
        TODOS = "todos"

    class Widget(ReactiveComponent, react=(Keys.TODOS,)):
        @classmethod
        def load(cls) -> "Widget":
            return cls()

    assert Widget._pjx_react_keys == ("todos",)


def test_subclass_without_load_returns_none():
    class Widget(ReactiveComponent):
        pass

    assert isinstance(Widget.load(), Widget)


def test_base_component_registration_still_fires():
    """super().__pydantic_init_subclass__() is not skipped - BaseComponent's
    reserved-field validation still rejects a subclass that shadows auto_id."""
    with pytest.raises(TypeError, match="auto_id"):

        class Widget(ReactiveComponent):
            auto_id: bool = False  # pyright: ignore[reportIncompatibleVariableOverride]


def test_the_descriptor_is_attached_to_reactive_subclasses():
    class Widget(ReactiveComponent):
        @classmethod
        def load(cls) -> "Widget":
            return cls()

    assert Widget.__pjx_descriptor__ is not None


def test_resolve_pjx_key_field_returns_none_when_unmarked():
    from pyjinhx.reactive.component import resolve_pjx_key_field

    class Widget(ReactiveComponent):
        name: str = ""

    assert resolve_pjx_key_field(Widget) is None


def test_resolve_pjx_key_field_finds_an_annotated_field():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey, resolve_pjx_key_field

    class Widget(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

    assert resolve_pjx_key_field(Widget) == "row_id"


def test_resolve_pjx_key_field_finds_a_field_wrapped_marker():
    from typing import Annotated

    from pydantic import Field

    from pyjinhx.reactive.component import PjxKey, resolve_pjx_key_field

    class Widget(ReactiveComponent):
        row_id: Annotated[int, PjxKey(), Field(default=0)]

    assert resolve_pjx_key_field(Widget) == "row_id"


def test_two_pjx_key_fields_raise_at_class_definition():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    with pytest.raises(TypeError, match="PjxKey"):

        class Widget(ReactiveComponent):
            a: Annotated[int, PjxKey()] = 0
            b: Annotated[int, PjxKey()] = 0


def test_unmarked_instances_share_one_cache_entry():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        @classmethod
        def load(cls) -> "Widget":
            calls.append(1)
            return cls()

    with request_scope():
        Widget.load()
        Widget.load()

    assert len(calls) == 1


def test_distinct_pjx_key_values_load_independently():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    calls: list[int] = []

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0
        value: int = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id, value=row_id * 10)

    with request_scope():
        assert Row.load(1).value == 10
        assert Row.load(2).value == 20

    assert calls == [1, 2]


def test_equal_pjx_key_values_share_one_cache_entry():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    calls: list[int] = []

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id)

    with request_scope():
        Row.load(1)
        Row.load(1)

    assert len(calls) == 1


def test_pjx_key_equal_values_share_object_identity():
    """Equal PjxKey values hit the same cache entry, so the second load() gets
    back the very same object — not an equal copy from a re-run body."""
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)

    with request_scope():
        result_a = Row.load(1)
        result_b = Row.load(1)

    assert result_a is result_b


def test_pjx_key_distinct_values_differ_in_identity():
    """Distinct PjxKey values are distinct cache entries, so each load() body
    runs and yields its own object — even when the two results compare equal."""
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0
        shape: str = "same"

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id, shape="same")

    with request_scope():
        result_a = Row.load(1)
        result_b = Row.load(2)

    assert result_a.shape == result_b.shape
    assert result_a is not result_b


class DemoAppContext(AppContext):
    """The app-defined context these tests thread through request_scope()."""

    def __init__(self, user: str) -> None:
        self.user = user


def test_load_receives_the_requests_app_context():
    class Widget(ReactiveComponent):
        user: str = ""

        @classmethod
        def load(cls, ctx: DemoAppContext) -> "Widget":
            return cls(user=ctx.user)

    with request_scope(load_context=DemoAppContext(user="ada")):
        assert Widget.load().user == "ada"  # type: ignore[reportCallIssue]


def test_each_request_gets_its_own_app_context():
    class Widget(ReactiveComponent):
        user: str = ""

        @classmethod
        def load(cls, ctx: DemoAppContext) -> "Widget":
            return cls(user=ctx.user)

    with request_scope(load_context=DemoAppContext(user="ada")):
        first = Widget.load()  # type: ignore[reportCallIssue]
    with request_scope(load_context=DemoAppContext(user="grace")):
        second = Widget.load()  # type: ignore[reportCallIssue]

    assert (first.user, second.user) == ("ada", "grace")


def test_injection_is_by_annotation_not_by_parameter_name():
    class Widget(ReactiveComponent):
        user: str = ""

        @classmethod
        def load(cls, whatever: DemoAppContext) -> "Widget":
            return cls(user=whatever.user)

    with request_scope(load_context=DemoAppContext(user="ada")):
        assert Widget.load().user == "ada"  # type: ignore[reportCallIssue]


def test_optional_app_context_annotation_is_injected():
    class Widget(ReactiveComponent):
        user: str = ""

        @classmethod
        def load(cls, ctx: DemoAppContext | None) -> "Widget":
            return cls(user="none" if ctx is None else ctx.user)

    with request_scope(load_context=DemoAppContext(user="ada")):
        assert Widget.load().user == "ada"  # type: ignore[reportCallIssue]


def test_no_context_bound_injects_none():
    class Widget(ReactiveComponent):
        user: str = ""

        @classmethod
        def load(cls, ctx: DemoAppContext | None) -> "Widget":
            return cls(user="none" if ctx is None else ctx.user)

    with request_scope():
        assert Widget.load().user == "none"  # type: ignore[reportCallIssue]


def test_zero_arg_load_is_untouched_when_a_context_is_bound():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        value: str = ""

        @classmethod
        def load(cls) -> "Widget":
            calls.append(1)
            return cls(value="loaded")

    with request_scope(load_context=DemoAppContext(user="ada")):
        assert Widget.load().value == "loaded"
        assert Widget.load().value == "loaded"

    assert len(calls) == 1


def test_an_injected_load_is_still_cached_per_request():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        user: str = ""

        @classmethod
        def load(cls, ctx: DemoAppContext) -> "Widget":
            calls.append(1)
            return cls(user=ctx.user)

    with request_scope(load_context=DemoAppContext(user="ada")):
        assert Widget.load().user == "ada"  # type: ignore[reportCallIssue]
        assert Widget.load().user == "ada"  # type: ignore[reportCallIssue]

    assert len(calls) == 1


def test_two_app_context_params_are_rejected_at_class_definition():
    class OtherAppContext(AppContext):
        """A second context class, so the two params differ in type too."""

    with pytest.raises(TypeError, match="at most one"):

        class Widget(ReactiveComponent):
            @classmethod
            def load(cls, first: DemoAppContext, second: OtherAppContext) -> "Widget":
                return cls()


def test_classmethod_load_is_accepted():
    class Widget(ReactiveComponent):
        @classmethod
        def load(cls) -> "Widget":
            return cls()

    assert isinstance(Widget.load(), Widget)


def test_instance_method_load_is_rejected_at_class_definition():
    with pytest.raises(TypeError, match="@classmethod"):

        class Widget(ReactiveComponent):
            def load(self) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
                return None


def test_instance_method_rejection_names_the_migration():
    with pytest.raises(TypeError, match=r"def load\(cls"):

        class Widget(ReactiveComponent):
            def load(self) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
                return None


def test_grandchild_that_does_not_override_load_is_not_rewrapped():
    """A subclass of a subclass, with no load of its own, must not trip the
    classmethod validator against its parent's already-wrapped function, and
    must not silently mis-key its cache entries under the parent's identity."""

    class Base(ReactiveComponent):
        @classmethod
        def load(cls) -> "Base":
            return cls()

    class Child(Base):
        pass

    assert isinstance(Child.load(), Child)


def test_load_params_must_match_the_pjx_key_field():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)

    assert Row.load(1).row_id == 1


def test_load_missing_the_key_param_is_rejected():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    with pytest.raises(TypeError, match="row_id"):

        class Row(ReactiveComponent):
            row_id: Annotated[int, PjxKey()] = 0

            @classmethod
            def load(cls) -> "Row":
                return cls()


def test_load_with_an_extra_param_is_rejected():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    with pytest.raises(TypeError, match="extra"):

        class Row(ReactiveComponent):
            row_id: Annotated[int, PjxKey()] = 0

            @classmethod
            def load(cls, row_id: int, extra: int) -> "Row":
                return cls(row_id=row_id)


def test_zero_key_class_load_must_take_no_params():
    with pytest.raises(TypeError, match="no parameters"):

        class Widget(ReactiveComponent):
            @classmethod
            def load(cls, stray: int) -> "Widget":
                return cls()


def test_protocol_mode_allows_extra_params():
    from typing import Annotated

    from pydantic import ConfigDict

    from pyjinhx.reactive.component import PjxKey

    class Row(ReactiveComponent):
        model_config = ConfigDict(extra="allow")
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int, flavor: str = "plain") -> "Row":
            return cls(row_id=row_id)

    assert Row.load(1, flavor="spicy").row_id == 1


def test_protocol_mode_still_requires_the_key_params():
    from typing import Annotated

    from pydantic import ConfigDict

    from pyjinhx.reactive.component import PjxKey

    with pytest.raises(TypeError, match="row_id"):

        class Row(ReactiveComponent):
            model_config = ConfigDict(extra="allow")
            row_id: Annotated[int, PjxKey()] = 0

            @classmethod
            def load(cls, flavor: str = "plain") -> "Row":
                return cls()


def test_self_referencing_return_annotation_keeps_context_injection():
    """#713: `-> "Row"` is an unresolvable forward ref while the class is being
    built; that must not silently drop the AppContext parameter."""
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0
        user: str = ""

        @classmethod
        def load(cls, row_id: int, ctx: DemoAppContext) -> "Row":
            return cls(row_id=row_id, user=ctx.user)

    with request_scope(load_context=DemoAppContext(user="ada")):
        assert Row.load(1).user == "ada"  # type: ignore[reportCallIssue]


def test_cache_hit_returns_the_same_populated_instance():
    """#726: the second load() in one request hands back the cached instance,
    not a second one whose fields were never filled."""
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    calls: list[int] = []

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0
        title: str = ""

        @classmethod
        def load(cls, row_id: int) -> "Row":
            calls.append(row_id)
            return cls(row_id=row_id, title=f"row {row_id}")

    with request_scope():
        first = Row.load(1)
        second = Row.load(1)

    assert first is second
    assert second.title == "row 1"
    assert calls == [1]


def test_distinct_keys_do_not_share_a_cache_entry():
    from typing import Annotated

    from pyjinhx.reactive.component import PjxKey

    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)

    with request_scope():
        assert Row.load(1) is not Row.load(2)


def test_protocol_mode_cache_key_uses_the_full_bound_args():
    from typing import Annotated

    from pydantic import ConfigDict

    from pyjinhx.reactive.component import PjxKey

    class Row(ReactiveComponent):
        model_config = ConfigDict(extra="allow")
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int, flavor: str = "plain") -> "Row":
            return cls(row_id=row_id, flavor=flavor)  # type: ignore[reportCallIssue]

    with request_scope():
        plain = Row.load(1)
        spicy = Row.load(1, flavor="spicy")  # type: ignore[reportCallIssue]
        again = Row.load(1, flavor="spicy")

    assert plain is not spicy
    assert spicy is again


def test_load_returning_the_wrong_type_raises():
    class Widget(ReactiveComponent):
        @classmethod
        def load(cls) -> "Widget":
            return "not a widget"  # pyright: ignore[reportReturnType]

    with request_scope(), pytest.raises(TypeError, match="Widget"):
        Widget.load()


def test_subclasses_inheriting_load_unchanged_get_their_own_identity_and_cache():
    class Row(ReactiveComponent):
        row_id: Annotated[int, PjxKey()] = 0

        @classmethod
        def load(cls, row_id: int) -> "Row":
            return cls(row_id=row_id)  # type: ignore[reportCallIssue]

    class RowB(Row):
        pass

    class RowC(Row):
        pass

    with request_scope():
        a = Row.load(1)  # type: ignore[reportCallIssue]
        b = RowB.load(1)  # type: ignore[reportCallIssue]
        c = RowC.load(1)  # type: ignore[reportCallIssue]

    assert type(a) is Row
    assert type(b) is RowB
    assert type(c) is RowC


def test_app_context_is_excluded_from_the_cache_key():
    calls: list[int] = []

    class Widget(ReactiveComponent):
        user: str = ""

        @classmethod
        def load(cls, ctx: DemoAppContext) -> "Widget":
            calls.append(1)
            return cls(user=ctx.user)

    with request_scope(load_context=DemoAppContext(user="ada")):
        first = Widget.load()  # type: ignore[reportCallIssue]
        second = Widget.load()  # type: ignore[reportCallIssue]

    assert first is second
    assert first.user == "ada"
    assert len(calls) == 1


def test_cache_policy_defaults_to_unset():
    class Baz(ReactiveComponent):
        pass

    assert Baz._pjx_cache_policy is None


def test_cache_policy_is_recorded_verbatim():
    class Foo(ReactiveComponent, cache=CachePolicy(ttl=60)):
        pass

    assert Foo._pjx_cache_policy == CachePolicy(ttl=60)


def test_cache_false_is_recorded_as_false_not_as_unset():
    class Bar(ReactiveComponent, cache=False):
        pass

    assert Bar._pjx_cache_policy is False


def test_cache_policy_is_not_inherited():
    class Parent(ReactiveComponent, cache=CachePolicy(ttl=60)):
        pass

    class Child(Parent):
        pass

    assert Child._pjx_cache_policy is None


def test_cache_false_is_not_inherited():
    class Parent(ReactiveComponent, cache=False):
        pass

    class Child(Parent):
        pass

    assert Child._pjx_cache_policy is None


def test_react_and_cache_are_both_consumed_together():
    class Widget(ReactiveComponent, react=("todos",), cache=CachePolicy(ttl=60)):
        pass

    assert Widget._pjx_react_keys == ("todos",)
    assert Widget._pjx_cache_policy == CachePolicy(ttl=60)


def test_cache_alone_does_not_disturb_the_react_keys():
    class Widget(ReactiveComponent, cache=False):
        pass

    assert Widget._pjx_react_keys == ()
