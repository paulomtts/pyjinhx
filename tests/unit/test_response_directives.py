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


def test_reactive_response_flags_reswap_when_oob_only():
    from pyjinhx.reactive import ReactiveResponse

    with Registry.request_scope():
        ReactiveResponse()
        assert current_directives().reswap_none is True


def test_reactive_response_no_flag_with_primary_html():
    from pyjinhx.reactive import ReactiveResponse

    with Registry.request_scope():
        ReactiveResponse(html="<div>primary</div>")
        assert current_directives().reswap_none is False


@pytest.mark.no_request_scope  # opt out of the global request_scope autouse fixture
def test_reactive_response_flag_no_crash_without_scope():
    from pyjinhx.reactive import ReactiveResponse

    # No request scope: current_directives() is None — must not raise.
    out = ReactiveResponse(html="<p>x</p>")
    assert out == "<p>x</p>"
