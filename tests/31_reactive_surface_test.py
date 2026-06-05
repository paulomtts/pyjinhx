import logging
from typing import ClassVar

from pyjinhx import BaseComponent


def test_state_hash_is_stable_and_value_sensitive():
    a = BaseComponent(id="x")
    b = BaseComponent(id="x")
    assert a.state_hash() == b.state_hash()
    assert isinstance(a.state_hash(), str) and len(a.state_hash()) == 16
    assert BaseComponent(id="x", extra="v1").state_hash() != a.state_hash()


def test_reactive_component_is_detected():
    class Counter(BaseComponent):
        remaining: int = 0
        depends_on: ClassVar[set[str]] = {"todos"}

        @classmethod
        def load(cls):
            return cls(id="counter", remaining=0)

    assert Counter._pjx_reactive is True
    assert Counter._pjx_depends_on == frozenset({"todos"})


def test_depends_on_is_not_a_model_field():
    class Widget(BaseComponent):
        depends_on: ClassVar[set[str]] = {"todos"}

        @classmethod
        def load(cls):
            return cls(id="w")

    assert "depends_on" not in Widget.model_fields
    assert Widget(id="w").id == "w"


def test_unannotated_depends_on_assignment_works():
    # Matches the exact syntax shown in issue #12.
    class Plain(BaseComponent):
        depends_on = {"todos"}

        @classmethod
        def load(cls):
            return cls(id="p")

    assert "depends_on" not in Plain.model_fields
    assert Plain._pjx_depends_on == frozenset({"todos"})


def test_plain_component_is_not_reactive():
    class Static(BaseComponent):
        pass

    assert Static._pjx_reactive is False
    assert Static._pjx_depends_on == frozenset()


def test_warns_when_load_without_depends_on(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):

        class Inert(BaseComponent):
            @classmethod
            def load(cls):
                return cls(id="i")

    assert any(
        "Inert" in r.message and "depends_on" in r.message for r in caplog.records
    )


def test_warns_when_depends_on_without_load(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):

        class NoLoad(BaseComponent):
            depends_on: ClassVar[set[str]] = {"todos"}

    assert any("NoLoad" in r.message and "load()" in r.message for r in caplog.records)
