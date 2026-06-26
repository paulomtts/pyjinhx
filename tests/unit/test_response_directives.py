from types import SimpleNamespace

import pytest

from pyjinhx import Registry
from pyjinhx.client import ClientBackend, ResponseDirectives, current_directives


@pytest.mark.no_request_scope
def test_directives_none_outside_request_scope():
    assert current_directives() is None


def test_directives_present_and_fresh_inside_request_scope():
    with Registry.request_scope():
        d = current_directives()
        assert isinstance(d, ResponseDirectives)
        assert d.reswap_none is False


@pytest.mark.no_request_scope
def test_directives_reset_after_request_scope():
    with Registry.request_scope():
        current_directives().reswap_none = True
    assert current_directives() is None


def test_directives_headers_maps_reswap_none():
    assert ResponseDirectives().headers() == {}
    assert ResponseDirectives(reswap_none=True).headers() == {"HX-Reswap": "none"}


class _StubBackend(ClientBackend):
    """A custom backend that only implements the abstract request side."""

    def get_header(self, name: str) -> str | None:
        return None


def test_apply_response_directives_sets_reswap_when_flagged():
    backend = _StubBackend()
    response = SimpleNamespace(headers={})
    with Registry.request_scope():
        current_directives().reswap_none = True
        backend.apply_response_directives(response)
    assert response.headers == {"HX-Reswap": "none"}


def test_apply_response_directives_noop_when_not_flagged():
    backend = _StubBackend()
    response = SimpleNamespace(headers={})
    with Registry.request_scope():
        backend.apply_response_directives(response)
    assert response.headers == {}


@pytest.mark.no_request_scope  # opt out of the global request_scope autouse fixture
def test_apply_response_directives_noop_without_request_scope():
    backend = _StubBackend()
    response = SimpleNamespace(headers={})
    backend.apply_response_directives(response)  # current_directives() is None
    assert response.headers == {}
