"""The too-cheap heuristic: which classes the render cache declines to touch.

A cache hit costs a key, a backend read, an unpickle and an asset replay —
around 20us for a small component. A template cheaper than that to render loses
by being cached, so the render path measures each class once and remembers.
"""

import pytest

from pyjinhx._component import BaseComponent
from pyjinhx.reactive.backend import CachePolicy
from pyjinhx.render_cache import (
    is_too_cheap,
    note_render_cost,
    reset_render_cost_decisions,
)


class _Cheap(BaseComponent):
    label: str = "hi"


class _Pricey(BaseComponent):
    label: str = "hi"


class _Explicit(BaseComponent, cache=CachePolicy(ttl=30)):
    label: str = "hi"


@pytest.fixture(autouse=True)
def own_threshold(monkeypatch: pytest.MonkeyPatch):
    """This file sets its own floor; the suite-wide zero would disarm every test."""
    monkeypatch.setenv("PJX_RENDER_CACHE_MIN_US", "150")
    reset_render_cost_decisions()


def test_a_render_under_the_floor_marks_the_class_too_cheap():
    note_render_cost(_Cheap, 12.0)
    assert is_too_cheap(_Cheap)


def test_a_render_over_the_floor_leaves_the_class_cacheable():
    note_render_cost(_Pricey, 900.0)
    assert not is_too_cheap(_Pricey)


def test_the_first_measurement_decides_and_later_ones_do_not_move_it():
    # Re-measuring would let a class flip between requests on machine load
    # alone, making the store's contents depend on scheduling noise.
    note_render_cost(_Cheap, 12.0)
    note_render_cost(_Cheap, 5000.0)
    assert is_too_cheap(_Cheap)


def test_an_unmeasured_class_is_not_too_cheap():
    # Absence of a verdict is "cache it", so the first render is never skipped.
    assert not is_too_cheap(_Pricey)


def test_the_floor_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PJX_RENDER_CACHE_MIN_US", "5")
    note_render_cost(_Cheap, 12.0)
    assert not is_too_cheap(_Cheap)


def test_a_non_numeric_floor_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PJX_RENDER_CACHE_MIN_US", "soon")
    with pytest.raises(ValueError, match="microseconds"):
        note_render_cost(_Cheap, 12.0)


def test_reset_forgets_every_verdict():
    note_render_cost(_Cheap, 12.0)
    reset_render_cost_decisions()
    assert not is_too_cheap(_Cheap)


def test_two_classes_are_judged_independently():
    note_render_cost(_Cheap, 12.0)
    note_render_cost(_Pricey, 900.0)
    assert is_too_cheap(_Cheap)
    assert not is_too_cheap(_Pricey)


def test_an_explicit_policy_class_can_still_be_measured_as_cheap():
    # The heuristic records what it saw; honoring the override is render_level's
    # job, so the verdict itself stays a plain measurement.
    note_render_cost(_Explicit, 12.0)
    assert is_too_cheap(_Explicit)
