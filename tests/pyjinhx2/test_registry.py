"""Tests for the discovery class registry and its built-then-swap publish."""

from pathlib import Path

import pytest

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent
from pyjinhx2.discovery import build_registry, get_class

DISCOVERY_DIR = Path(__file__).parent.parent / "templates" / "discovery"


class AlphaCard(BaseComponent):
    pass


class NestedWidget(BaseComponent):
    pass


class Unrelated(BaseComponent):
    pass


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test starts from an empty published mapping."""
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = {}


def test_registry_is_empty_before_any_build():
    assert get_class("alpha_card") is None


def test_get_class_returns_none_for_unknown_tag_never_raises():
    assert get_class("no_such_tag_anywhere") is None
    assert get_class("") is None


def test_registry_state_is_not_a_bare_module_level_container():
    """The purity scan in test_discovery.py flags dict/list/set module globals.
    Registry state must be owned by a holder object so the walk stays visibly
    stateless."""
    mutable = [
        name
        for name, value in vars(discovery).items()
        if isinstance(value, (dict, list, set)) and not name.startswith("__")
    ]
    assert mutable == []


def test_build_registers_classes_whose_tag_is_on_disk():
    build_registry(DISCOVERY_DIR, [AlphaCard, NestedWidget])
    assert get_class("alpha_card") is AlphaCard
    assert get_class("nested_widget") is NestedWidget


def test_build_skips_classes_with_no_template_on_disk():
    build_registry(DISCOVERY_DIR, [AlphaCard, Unrelated])
    assert get_class("unrelated") is None


def test_build_skips_templates_with_no_matching_class():
    build_registry(DISCOVERY_DIR, [AlphaCard])
    assert get_class("deep_widget") is None
    assert get_class("beta") is None


def test_build_accepts_str_template_dir():
    build_registry(str(DISCOVERY_DIR), [AlphaCard])
    assert get_class("alpha_card") is AlphaCard


def test_rebuild_replaces_the_previous_mapping_entirely():
    build_registry(DISCOVERY_DIR, [AlphaCard, NestedWidget])
    build_registry(DISCOVERY_DIR, [NestedWidget])
    assert get_class("nested_widget") is NestedWidget
    assert get_class("alpha_card") is None
