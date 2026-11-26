"""Fixtures shared by the split test files in this folder."""

import pytest

from pyjinhx.components import discovery


@pytest.fixture(autouse=True)
def empty_registry():
    discovery._registry.mapping = {}
    yield
    discovery._registry.mapping = {}
