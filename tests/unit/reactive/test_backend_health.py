"""Per-backend failure state: log once, degrade on evict, heal on a write."""

import logging

import pytest

from pyjinhx.reactive.backend_health import (
    is_degraded,
    note_failure,
    note_write_success,
    reset_backend_health,
)


class FakeBackend:
    """A stand-in backend: health state never calls into it, only keys on it."""


@pytest.fixture(autouse=True)
def clean_health():
    """Every test starts and ends with no recorded backend health."""
    reset_backend_health()
    yield
    reset_backend_health()


def test_a_fresh_backend_is_not_degraded():
    assert is_degraded(FakeBackend()) is False


def test_a_get_failure_does_not_degrade_the_backend():
    backend = FakeBackend()

    note_failure(backend, "get", RuntimeError("boom"), degrade=False)

    assert is_degraded(backend) is False


def test_an_evict_failure_degrades_the_backend():
    backend = FakeBackend()

    note_failure(backend, "evict", RuntimeError("boom"), degrade=True)

    assert is_degraded(backend) is True


def test_a_successful_write_clears_the_degraded_flag():
    backend = FakeBackend()
    note_failure(backend, "evict", RuntimeError("boom"), degrade=True)

    note_write_success(backend)

    assert is_degraded(backend) is False


def test_a_successful_write_on_a_healthy_backend_is_a_no_op():
    backend = FakeBackend()

    note_write_success(backend)

    assert is_degraded(backend) is False


def test_only_the_first_failure_of_a_backend_is_logged(
    caplog: pytest.LogCaptureFixture,
):
    backend = FakeBackend()

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        note_failure(backend, "get", RuntimeError("boom"), degrade=False)
        note_failure(backend, "get", RuntimeError("boom again"), degrade=False)
        note_failure(backend, "evict", RuntimeError("and again"), degrade=True)

    assert len(caplog.records) == 1
    assert "FakeBackend" in caplog.records[0].getMessage()
    assert "get" in caplog.records[0].getMessage()


def test_two_backend_instances_keep_independent_state(
    caplog: pytest.LogCaptureFixture,
):
    first = FakeBackend()
    second = FakeBackend()

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        note_failure(first, "evict", RuntimeError("boom"), degrade=True)
        note_failure(second, "get", RuntimeError("boom"), degrade=False)

    assert is_degraded(first) is True
    assert is_degraded(second) is False
    assert len(caplog.records) == 2


def test_reset_clears_every_backends_state(caplog: pytest.LogCaptureFixture):
    backend = FakeBackend()
    note_failure(backend, "evict", RuntimeError("boom"), degrade=True)

    reset_backend_health()

    assert is_degraded(backend) is False
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        note_failure(backend, "evict", RuntimeError("boom"), degrade=True)
    assert len(caplog.records) == 1
