"""Combined-matrix tests for discovery: orphan, plain duplicate and pjx_replace
resolution all inside one `build_registry` call.

The per-feature files each drive one axis at a time — `test_discovery.py` the
walk, `test_registry.py` the registry and duplicate warning, `test_replace.py`
the override. Verified before writing this file: none of them asserts an
orphan tag and a replace resolution in the same build, and `test_registry.py`
never mentions `pjx_replace`. That interaction is what is checked here: one
build, one published mapping, one warning.
"""

import logging
from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx._component import BaseComponent
from pyjinhx.discovery import build_registry, get_class

DISCOVERY_DIR = Path(__file__).parent.parent / "templates" / "discovery"


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test starts from an empty published mapping."""
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = {}


def _matrix_classes():
    """One class set that hits every axis at once against DISCOVERY_DIR.

    `alpha_card` collides with no replacer, `deep_widget` collides with one,
    `nested_widget` is uncontested and `beta.pjx` is left with no class at all.
    Class names are reassigned after definition so two classes can claim one
    tag; the collision tie-break reads `__qualname__`, which keeps the
    original names, so `Bbb...` sorts after `Aaa...` and wins.
    """

    class AaaAlphaCard(BaseComponent):
        pass

    class BbbAlphaCard(BaseComponent):
        pass

    class PlainDeepWidget(BaseComponent):
        pass

    class ReplacingDeepWidget(BaseComponent, pjx_replace=True):
        pass

    class NestedWidget(BaseComponent):
        pass

    AaaAlphaCard.__name__ = "AlphaCard"
    BbbAlphaCard.__name__ = "AlphaCard"
    PlainDeepWidget.__name__ = "DeepWidget"
    ReplacingDeepWidget.__name__ = "DeepWidget"
    return (
        AaaAlphaCard,
        BbbAlphaCard,
        PlainDeepWidget,
        ReplacingDeepWidget,
        NestedWidget,
    )


def test_one_build_resolves_orphan_duplicate_and_replace_together():
    aaa_alpha, bbb_alpha, plain_deep, replacing_deep, nested = _matrix_classes()

    build_registry(
        DISCOVERY_DIR, [aaa_alpha, plain_deep, nested, replacing_deep, bbb_alpha]
    )

    assert get_class("beta") is None
    assert get_class("alpha_card") is bbb_alpha
    assert get_class("deep_widget") is replacing_deep
    assert get_class("nested_widget") is nested


def test_combined_build_warns_once_and_only_for_the_plain_duplicate(caplog):
    aaa_alpha, bbb_alpha, plain_deep, replacing_deep, nested = _matrix_classes()

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        build_registry(
            DISCOVERY_DIR, [aaa_alpha, plain_deep, nested, replacing_deep, bbb_alpha]
        )

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "alpha_card" in message
    assert "deep_widget" not in message
    assert "beta" not in message
    assert "nested_widget" not in message


def test_replace_resolution_does_not_suppress_an_unrelated_duplicate(caplog):
    """The `warned` set is per build, not per tag pair: a silent replace on one
    tag must not stop the plain collision on another from being reported, and
    each tag must still resolve on its own rules."""
    aaa_alpha, bbb_alpha, plain_deep, replacing_deep, _ = _matrix_classes()

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        build_registry(
            DISCOVERY_DIR, [replacing_deep, aaa_alpha, plain_deep, bbb_alpha]
        )

    assert get_class("deep_widget") is replacing_deep
    assert get_class("alpha_card") is bbb_alpha
    assert len(caplog.records) == 1
    assert "alpha_card" in caplog.records[0].getMessage()


def test_combined_build_adds_no_module_level_mutable_state():
    """Same scan the other three files run — a build that touches every axis
    must still leave the module namespace free of stray containers."""
    build_registry(DISCOVERY_DIR, list(_matrix_classes()))

    mutable = [
        name
        for name, value in vars(discovery).items()
        if isinstance(value, (dict, list, set)) and not name.startswith("__")
    ]
    assert mutable == []
