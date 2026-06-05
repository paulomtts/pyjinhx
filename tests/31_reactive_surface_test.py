from typing import ClassVar

import pytest

from pyjinhx import BaseComponent, ReactiveComponent


class GoodCounter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "GoodCounter":
        return cls(id="counter", remaining=0)


def test_state_hash_is_stable_and_value_sensitive():
    a = GoodCounter(id="x", remaining=1)
    b = GoodCounter(id="x", remaining=1)
    assert a.state_hash() == b.state_hash()
    assert isinstance(a.state_hash(), str) and len(a.state_hash()) == 16
    assert GoodCounter(id="x", remaining=2).state_hash() != a.state_hash()


def test_reactive_component_is_detected():
    assert GoodCounter._pjx_reactive is True
    assert GoodCounter._pjx_reacts_to == frozenset({"todos"})


def test_reacts_to_is_not_a_model_field():
    assert "reacts_to" not in GoodCounter.model_fields
    assert GoodCounter(id="c", remaining=3).remaining == 3


def test_unannotated_reacts_to_assignment_works():
    class Plain(ReactiveComponent):
        reacts_to = {"todos"}

        @classmethod
        def load(cls):
            return cls(id="p")

    assert "reacts_to" not in Plain.model_fields
    assert Plain._pjx_reacts_to == frozenset({"todos"})


def test_plain_basecomponent_is_not_reactive():
    class Static(BaseComponent):
        pass

    assert getattr(Static, "_pjx_reactive", False) is False
    assert getattr(Static, "_pjx_reacts_to", frozenset()) == frozenset()


def test_stray_load_on_basecomponent_is_not_reactive():
    # Duck-typing is gone: a load() on a plain BaseComponent does NOT make it reactive.
    class HasLoad(BaseComponent):
        @classmethod
        def load(cls):
            return cls(id="h")

    assert getattr(HasLoad, "_pjx_reactive", False) is False


def test_load_without_reacts_to_raises_at_definition():
    with pytest.raises(TypeError, match="reacts_to"):

        class Inert(ReactiveComponent):
            @classmethod
            def load(cls):
                return cls(id="i")


def test_reacts_to_without_load_cannot_be_instantiated():
    class NoLoad(ReactiveComponent):
        reacts_to: ClassVar[set[str]] = {"todos"}

    with pytest.raises(TypeError, match="abstract"):
        NoLoad(id="n")


def test_reactive_component_base_is_abstract():
    with pytest.raises(TypeError, match="abstract"):
        ReactiveComponent(id="r")
