import pytest

from pyjinhx import Registry
from pyjinhx.client import ResponseDirectives, current_directives


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
