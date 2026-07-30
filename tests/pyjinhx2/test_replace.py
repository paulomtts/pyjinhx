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
