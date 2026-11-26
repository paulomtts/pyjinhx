"""Tests for app-context injection into load(), load() signature validation and cache and retain policies."""

from typing import Annotated

import pytest

from pyjinhx.app_context import AppContext
from pyjinhx.reactive.backend import CachePolicy
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.rendering.session import request_scope


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


def test_retain_across_parent_swaps_defaults_to_true():
    assert ReactiveComponent.retain_across_parent_swaps is True


def test_retain_across_parent_swaps_is_inherited_by_a_silent_subclass():
    class Widget(ReactiveComponent):
        pass

    assert Widget.retain_across_parent_swaps is True
    assert Widget().retain_across_parent_swaps is True


def test_a_subclass_can_opt_out_of_retain_across_parent_swaps_without_mutating_the_base():
    class Widget(ReactiveComponent):
        retain_across_parent_swaps = False

    class Child(Widget):
        pass

    assert Widget.retain_across_parent_swaps is False
    assert Child.retain_across_parent_swaps is False
    assert ReactiveComponent.retain_across_parent_swaps is True


def test_sibling_subclasses_set_retain_across_parent_swaps_independently():
    class OptedOut(ReactiveComponent):
        retain_across_parent_swaps = False

    class Silent(ReactiveComponent):
        pass

    assert OptedOut.retain_across_parent_swaps is False
    assert Silent.retain_across_parent_swaps is True
