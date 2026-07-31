"""Tests for the pjx_replace override: the class kwarg and how discovery
resolves a tag when one of the colliding classes opts in as the replacement."""

import logging
from pathlib import Path

import pytest

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent
from pyjinhx2.discovery import build_registry, get_class

DISCOVERY_DIR = Path(__file__).parent.parent / "templates" / "discovery"


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test starts from an empty published mapping."""
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = {}


def test_plain_component_does_not_want_replace():
    class PlainThing(BaseComponent):
        pass

    assert PlainThing._pjx_replace is False


def test_component_declaring_the_kwarg_wants_replace():
    class ReplacingThing(BaseComponent, pjx_replace=True):
        pass

    assert ReplacingThing._pjx_replace is True


def test_replace_false_is_accepted_explicitly():
    class NotReplacingThing(BaseComponent, pjx_replace=False):
        pass

    assert NotReplacingThing._pjx_replace is False


def test_replace_flag_does_not_leak_to_subclasses():
    class ReplacingBase(BaseComponent, pjx_replace=True):
        pass

    class QuietChild(ReplacingBase):
        pass

    assert ReplacingBase._pjx_replace is True
    assert QuietChild._pjx_replace is False


def test_replace_kwarg_does_not_become_a_model_field():
    class FlaggedThing(BaseComponent, pjx_replace=True):
        pass

    assert "pjx_replace" not in FlaggedThing.model_fields
    assert "_pjx_replace" not in FlaggedThing.model_fields


def test_explicit_replace_wins_the_tag():
    class AlphaCard(BaseComponent):
        pass

    class ZzzOriginalAlphaCard(BaseComponent):
        pass

    ZzzOriginalAlphaCard.__name__ = "AlphaCard"

    build_registry(DISCOVERY_DIR, [AlphaCard, ZzzOriginalAlphaCard])
    assert get_class("alpha_card") is ZzzOriginalAlphaCard

    class ReplacingAlphaCard(BaseComponent, pjx_replace=True):
        pass

    ReplacingAlphaCard.__name__ = "AlphaCard"

    build_registry(DISCOVERY_DIR, [AlphaCard, ZzzOriginalAlphaCard, ReplacingAlphaCard])
    assert get_class("alpha_card") is ReplacingAlphaCard


def test_explicit_replace_does_not_warn(caplog):
    class AlphaCard(BaseComponent):
        pass

    class ReplacingAlphaCard(BaseComponent, pjx_replace=True):
        pass

    ReplacingAlphaCard.__name__ = "AlphaCard"

    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [AlphaCard, ReplacingAlphaCard])

    assert caplog.records == []
    assert get_class("alpha_card") is ReplacingAlphaCard


def test_replace_with_no_collision_is_a_no_op(caplog):
    class NestedWidget(BaseComponent, pjx_replace=True):
        pass

    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [NestedWidget])

    assert caplog.records == []
    assert get_class("nested_widget") is NestedWidget


def test_two_competing_replacers_resolve_deterministically(caplog):
    class AaaAlphaCard(BaseComponent, pjx_replace=True):
        pass

    class BbbAlphaCard(BaseComponent, pjx_replace=True):
        pass

    AaaAlphaCard.__name__ = "AlphaCard"
    BbbAlphaCard.__name__ = "AlphaCard"

    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [AaaAlphaCard, BbbAlphaCard])
    first = get_class("alpha_card")
    assert len(caplog.records) == 1
    assert "alpha_card" in caplog.records[0].getMessage()
    caplog.clear()

    # `pyjinhx2` already sits at the default WARNING level (verified: a
    # `logger.warning` call is captured by caplog whether or not it runs
    # inside an `at_level` block), so the second build's own warning would
    # also land in caplog.records if not cleared above — clear first, then
    # this call only needs to prove the winner is order-independent.
    build_registry(DISCOVERY_DIR, [BbbAlphaCard, AaaAlphaCard])
    second = get_class("alpha_card")

    assert first is second is BbbAlphaCard


def test_non_replace_collision_still_warns_and_sorts(caplog):
    class AaaAlphaCard(BaseComponent):
        pass

    class BbbAlphaCard(BaseComponent):
        pass

    AaaAlphaCard.__name__ = "AlphaCard"
    BbbAlphaCard.__name__ = "AlphaCard"

    with caplog.at_level(logging.WARNING, logger="pyjinhx2"):
        build_registry(DISCOVERY_DIR, [BbbAlphaCard, AaaAlphaCard])

    assert get_class("alpha_card") is BbbAlphaCard
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING


def test_replace_adds_no_module_level_mutable_state():
    mutable = [
        name
        for name, value in vars(discovery).items()
        if isinstance(value, (dict, list, set)) and not name.startswith("__")
    ]
    assert mutable == []
