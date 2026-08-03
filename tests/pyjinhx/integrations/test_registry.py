"""The one-slot backend registry: no web framework required to exercise it."""

from __future__ import annotations

import pytest

from pyjinhx.integrations.base import (
    IntegrationBackend,
    get_backend,
    register_backend,
)


class StubBackend:
    """Minimal Protocol conformer, so the registry can be driven standalone."""

    def is_installed(self, app: object) -> bool:
        return False

    def mark_installed(self, app: object) -> None:
        return None

    def mount_static(self, app: object, directory: str) -> None:
        return None

    def on_startup(self, app: object) -> None:
        return None

    def on_shutdown(self, app: object) -> None:
        return None

    def to_response(self, result: object, request: object | None) -> object:
        return result


@pytest.fixture
def clean_registry():
    """Restore whatever backend the process already had registered."""
    from pyjinhx.integrations import base

    previous = base._backend
    yield
    base._backend = previous


def test_registering_a_backend_makes_it_retrievable(clean_registry) -> None:
    backend = StubBackend()
    register_backend(backend)
    assert get_backend() is backend


def test_registering_again_replaces_the_slot(clean_registry) -> None:
    first, second = StubBackend(), StubBackend()
    register_backend(first)
    register_backend(second)
    assert get_backend() is second


def test_no_backend_registered_returns_none(clean_registry) -> None:
    from pyjinhx.integrations import base

    base._backend = None
    assert get_backend() is None


def test_stub_backend_satisfies_the_protocol() -> None:
    assert isinstance(StubBackend(), IntegrationBackend)
