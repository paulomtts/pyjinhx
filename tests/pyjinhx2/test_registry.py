"""Tests for the discovery class registry and its built-then-swap publish."""

from pyjinhx2 import discovery
from pyjinhx2.discovery import get_class


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
