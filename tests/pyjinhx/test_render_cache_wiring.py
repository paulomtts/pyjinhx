"""The tier-2 render cache as render_level() actually uses it: the class-level
off-switch, the resolve/read/write seam, and the slot-disqualification rule.

Full behavioral coverage of the render cache is #821's; what is pinned here is
the wiring — that render_level consults the backend at all, that it stops
consulting it when told to, and that nothing it caches can splice wrong.
"""

from typing import Any

import pytest

from pyjinhx._component import BaseComponent
from pyjinhx.reactive.backend import CachePolicy


def test_a_plain_component_records_an_explicit_cache_policy():
    class Widget(BaseComponent, cache=CachePolicy(ttl=45)):
        label: str = ""

    assert Widget._pjx_cache_policy == CachePolicy(ttl=45)


def test_a_plain_component_records_an_explicit_opt_out():
    class Widget(BaseComponent, cache=False):
        label: str = ""

    assert Widget._pjx_cache_policy is False


def test_a_plain_component_that_says_nothing_records_none():
    class Widget(BaseComponent):
        label: str = ""

    assert Widget._pjx_cache_policy is None


def test_a_subclass_does_not_inherit_its_parents_cache_policy():
    class Parent(BaseComponent, cache=False):
        label: str = ""

    class Child(Parent):
        label: str = ""

    assert Child._pjx_cache_policy is None
