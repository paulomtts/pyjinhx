"""The per-class `load()`-cost verdict that decides whether fan-out threads a build."""

import pytest

from pyjinhx.reactive.load_cost import (
    _DEFAULT_MIN_COST_US,
    is_too_cheap_to_thread,
    note_load_cost,
    reset_load_cost_decisions,
)


class CheapLoad:
    pass


class OtherCheapLoad:
    pass


@pytest.fixture(autouse=True)
def _clean_decisions():
    reset_load_cost_decisions()
    yield
    reset_load_cost_decisions()


def test_unmeasured_class_is_not_too_cheap():
    assert is_too_cheap_to_thread(CheapLoad) is False


def test_cost_below_floor_marks_the_class_too_cheap():
    note_load_cost(CheapLoad, _DEFAULT_MIN_COST_US - 1.0)
    assert is_too_cheap_to_thread(CheapLoad) is True


def test_cost_at_the_floor_stays_worth_threading():
    note_load_cost(CheapLoad, _DEFAULT_MIN_COST_US)
    assert is_too_cheap_to_thread(CheapLoad) is False


def test_second_measurement_does_not_flip_the_verdict():
    note_load_cost(CheapLoad, _DEFAULT_MIN_COST_US - 1.0)
    note_load_cost(CheapLoad, _DEFAULT_MIN_COST_US * 100)
    assert is_too_cheap_to_thread(CheapLoad) is True


def test_reset_returns_a_class_to_the_unmeasured_state():
    note_load_cost(CheapLoad, 0.0)
    assert is_too_cheap_to_thread(CheapLoad) is True
    reset_load_cost_decisions()
    assert is_too_cheap_to_thread(CheapLoad) is False


def test_verdicts_are_keyed_per_class_not_shared_by_shape():
    note_load_cost(CheapLoad, 0.0)
    assert is_too_cheap_to_thread(CheapLoad) is True
    assert is_too_cheap_to_thread(OtherCheapLoad) is False
