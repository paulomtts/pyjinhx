import re
from datetime import date
from enum import Enum

from pydantic import BaseModel

from pyjinhx.reactive.component import ReactiveComponent


class Status(str, Enum):
    OPEN = "open"
    DONE = "done"


class Card(ReactiveComponent):
    title: str = "hello"
    count: int = 0


class Dated(ReactiveComponent):
    when: date = date(2020, 1, 2)
    status: Status = Status.OPEN


class Loose(ReactiveComponent):
    title: str = "hello"
    count: int = 0

    state_hash_exclude = frozenset({"id", "count"})


class Inner(BaseModel):
    label: str = "a"
    weight: int = 1


class Collected(ReactiveComponent):
    tags: list[str] = []  # noqa: RUF012 — pydantic's own default-factory handling
    meta: dict[str, int] = {}  # noqa: RUF012 — pydantic's own default-factory handling
    inner: Inner = Inner()
    note: str | None = None


class Parent(ReactiveComponent):
    a: str = "a"
    b: str = "b"
    c: str = "c"


class Child(Parent):
    state_hash_exclude = frozenset({"id", "b"})


class GrandChild(Child):
    state_hash_exclude = frozenset({"id", "c"})


class MultiExcluded(ReactiveComponent):
    kept: str = "k"
    skip1: str = "1"
    skip2: str = "2"

    state_hash_exclude = frozenset({"id", "skip1", "skip2"})


def test_default_exclude_is_just_id():
    assert ReactiveComponent.state_hash_exclude == frozenset({"id"})


def test_same_field_values_with_different_ids_hash_the_same():
    assert (
        Card(id="a", title="x", count=1).state_hash()
        == Card(id="b", title="x", count=1).state_hash()
    )


def test_changing_a_non_excluded_field_changes_the_hash():
    assert (
        Card(title="x", count=1).state_hash() != Card(title="x", count=2).state_hash()
    )


def test_subclass_override_makes_the_hash_ignore_that_field():
    assert (
        Loose(title="x", count=1).state_hash() == Loose(title="x", count=2).state_hash()
    )
    assert (
        Loose(title="x", count=1).state_hash() != Loose(title="y", count=1).state_hash()
    )


def test_hash_is_a_64_char_lowercase_hex_digest():
    assert re.fullmatch(r"[0-9a-f]{64}", Card().state_hash())


def test_hash_is_stable_across_repeated_calls():
    card = Card(title="x", count=1)
    assert card.state_hash() == card.state_hash()


def test_non_json_native_field_types_hash_stably():
    assert Dated(id="a").state_hash() == Dated(id="b").state_hash()
    assert (
        Dated(when=date(2020, 1, 2)).state_hash()
        != Dated(when=date(2021, 1, 2)).state_hash()
    )


def test_hash_stable_across_repeated_calls_same_instance():
    collected = Collected(id="c1", tags=["a", "b"], meta={"x": 1})
    first = collected.state_hash()
    assert first == collected.state_hash() == collected.state_hash()


def test_hash_stable_across_distinct_instances_same_relevant_state():
    left = Collected(id="left", tags=["a"], meta={"x": 1}, inner=Inner(label="z"))
    right = Collected(id="right", tags=["a"], meta={"x": 1}, inner=Inner(label="z"))
    assert left.state_hash() == right.state_hash()


def test_dict_key_insertion_order_does_not_change_the_hash():
    """sort_keys is what makes an unchanged mapping hash the same."""
    forward = Collected(meta={"a": 1, "b": 2})
    reversed_ = Collected(meta={"b": 2, "a": 1})
    assert forward.state_hash() == reversed_.state_hash()


def test_list_append_changes_the_hash():
    base = Collected(tags=["a"])
    assert base.state_hash() != Collected(tags=["a", "b"]).state_hash()


def test_list_removal_changes_the_hash():
    assert Collected(tags=["a", "b"]).state_hash() != Collected(tags=["a"]).state_hash()


def test_list_reorder_changes_the_hash():
    """A list is ordered state: reordering it is a different render."""
    assert (
        Collected(tags=["a", "b"]).state_hash()
        != Collected(tags=["b", "a"]).state_hash()
    )


def test_empty_and_populated_list_hash_differently():
    assert Collected(tags=[]).state_hash() != Collected(tags=["a"]).state_hash()


def test_dict_value_mutation_changes_the_hash():
    assert (
        Collected(meta={"x": 1}).state_hash() != Collected(meta={"x": 2}).state_hash()
    )


def test_dict_key_rename_changes_the_hash():
    assert (
        Collected(meta={"x": 1}).state_hash() != Collected(meta={"y": 1}).state_hash()
    )


def test_empty_and_populated_dict_hash_differently():
    assert Collected(meta={}).state_hash() != Collected(meta={"x": 1}).state_hash()


def test_nested_model_field_change_changes_the_hash():
    assert (
        Collected(inner=Inner(label="a")).state_hash()
        != Collected(inner=Inner(label="b")).state_hash()
    )


def test_nested_model_untouched_field_keeps_the_hash():
    assert (
        Collected(inner=Inner(label="a", weight=1)).state_hash()
        == Collected(inner=Inner(label="a", weight=1)).state_hash()
    )


def test_optional_field_none_to_value_changes_the_hash():
    assert Collected(note=None).state_hash() != Collected(note="x").state_hash()


def test_optional_field_value_to_none_changes_the_hash():
    populated = Collected(note="x")
    assert populated.state_hash() != Collected(note=None).state_hash()


def test_in_place_mutation_of_a_list_field_changes_the_hash():
    """state_hash reads live field values, so a mutation between calls shows up."""
    collected = Collected(tags=["a"])
    before = collected.state_hash()
    collected.tags.append("b")
    assert collected.state_hash() != before


def test_parent_hashes_every_field_but_id():
    assert Parent(a="x").state_hash() != Parent(a="y").state_hash()
    assert Parent(b="x").state_hash() != Parent(b="y").state_hash()
    assert Parent(c="x").state_hash() != Parent(c="y").state_hash()


def test_child_exclude_hides_only_its_own_named_field():
    assert Child(b="x").state_hash() == Child(b="y").state_hash()
    assert Child(c="x").state_hash() != Child(c="y").state_hash()


def test_grandchild_exclude_replaces_rather_than_extends_the_parents():
    """A subclass's value wins outright: 'b' is hashed again, 'c' is not."""
    assert GrandChild(c="x").state_hash() == GrandChild(c="y").state_hash()
    assert GrandChild(b="x").state_hash() != GrandChild(b="y").state_hash()


def test_id_stays_excluded_at_every_level_of_the_chain():
    assert Parent(id="p1").state_hash() == Parent(id="p2").state_hash()
    assert Child(id="c1").state_hash() == Child(id="c2").state_hash()
    assert GrandChild(id="g1").state_hash() == GrandChild(id="g2").state_hash()


def test_multiple_excluded_fields_are_all_ignored():
    assert (
        MultiExcluded(skip1="a", skip2="b").state_hash()
        == MultiExcluded(skip1="z", skip2="z").state_hash()
    )


def test_excluded_field_ignored_regardless_of_value_type_or_size():
    """An excluded field can hold anything; the digest never moves."""
    base = MultiExcluded(kept="k").state_hash()
    assert MultiExcluded(kept="k", skip1="x" * 5000).state_hash() == base
    assert MultiExcluded(kept="k", skip1="").state_hash() == base


def test_a_class_that_excludes_nothing_hashes_its_id_too():
    class Bare(ReactiveComponent):
        state_hash_exclude = frozenset()

    assert Bare(id="one").state_hash() != Bare(id="two").state_hash()
