"""The per-class `load()`-cost verdict that decides whether fan-out threads a build."""

import pytest

from pyjinhx.reactive.load_cost import (
    _DEFAULT_MIN_COST_US,
    _min_cost_us,
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


def test_min_cost_defaults_when_the_env_var_is_absent(monkeypatch):
    monkeypatch.delenv("PJX_FANOUT_THREAD_MIN_US", raising=False)
    assert _min_cost_us() == _DEFAULT_MIN_COST_US


def test_empty_env_var_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("PJX_FANOUT_THREAD_MIN_US", "")
    assert _min_cost_us() == _DEFAULT_MIN_COST_US


def test_env_var_overrides_the_floor(monkeypatch):
    monkeypatch.setenv("PJX_FANOUT_THREAD_MIN_US", "42.5")
    assert _min_cost_us() == 42.5


def test_non_numeric_env_var_names_itself_and_the_value(monkeypatch):
    monkeypatch.setenv("PJX_FANOUT_THREAD_MIN_US", "abc")
    with pytest.raises(ValueError, match="PJX_FANOUT_THREAD_MIN_US.*abc"):
        _min_cost_us()


def test_env_var_is_re_read_on_every_call(monkeypatch):
    monkeypatch.setenv("PJX_FANOUT_THREAD_MIN_US", "10")
    assert _min_cost_us() == 10.0
    monkeypatch.setenv("PJX_FANOUT_THREAD_MIN_US", "20")
    assert _min_cost_us() == 20.0


def test_the_env_floor_decides_the_verdict(monkeypatch):
    monkeypatch.setenv("PJX_FANOUT_THREAD_MIN_US", "10")
    note_load_cost(CheapLoad, 50.0)
    assert is_too_cheap_to_thread(CheapLoad) is False


def test_build_dirty_records_a_verdict_for_the_loaded_class(monkeypatch):
    from pyjinhx.reactive import fanout

    monkeypatch.setenv("PJX_FANOUT_THREAD_MIN_US", "1000000")

    class Recorded:
        _pjx_key_field = None

        @classmethod
        def load(cls):
            return cls()

    monkeypatch.setattr(fanout, "render_level", lambda instance, session: "<div></div>")
    fanout._build_dirty(Recorded, "pjx-1", None, object())

    assert is_too_cheap_to_thread(Recorded) is True
