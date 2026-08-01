import re
from datetime import date
from enum import Enum

from pyjinhx2.reactive.component import ReactiveComponent


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
