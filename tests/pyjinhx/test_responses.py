"""The framework-free response layer: what one handler return composes into."""

import dataclasses
import typing

import pytest
from markupsafe import Markup

from pyjinhx import discovery
from pyjinhx._component import BaseComponent
from pyjinhx.responses import PASSTHROUGH, PjxResponse, compose
from pyjinhx.session import request_scope


class _Htmlish:
    def __html__(self) -> Markup:
        return Markup("<p>from-dunder-html</p>")


def test_a_string_return_becomes_the_primary_body():
    with request_scope():
        assert compose("<p>hi</p>") == PjxResponse(body="<p>hi</p>", headers={})


def test_the_body_is_a_plain_str_not_markup():
    """Backends serialize `.body` directly; Markup would leak escaping semantics."""
    with request_scope():
        assert type(compose("<p>hi</p>").body) is str


def test_a_dunder_html_return_is_adopted_without_escaping():
    with request_scope():
        assert compose(_Htmlish()).body == "<p>from-dunder-html</p>"


def test_a_none_return_is_an_empty_primary_and_asks_htmx_not_to_swap():
    with request_scope():
        composed = compose(None)
        assert composed.body == ""
        assert composed.headers == {"HX-Reswap": "none"}


def test_a_whitespace_only_primary_also_asks_htmx_not_to_swap():
    with request_scope():
        assert compose("   \n\t ").headers == {"HX-Reswap": "none"}


def test_the_default_status_is_200():
    with request_scope():
        assert compose("<p>hi</p>").status == 200


def test_an_unknown_return_type_passes_through():
    with request_scope():
        assert compose(object()) is PASSTHROUGH


def test_an_int_return_passes_through():
    with request_scope():
        assert compose(7) is PASSTHROUGH


def test_a_framework_response_object_passes_through():
    """This is the path a handler's own redirect takes: compose() does not
    recognise it, so it reaches the backend intact for translation. It is also
    how a caller asks for HX-Location, which has no status-code spelling."""

    class _FrameworkResponse:
        status_code: typing.ClassVar = 303
        headers: typing.ClassVar = {"location": "/elsewhere"}

    with request_scope():
        assert compose(_FrameworkResponse()) is PASSTHROUGH


def test_compose_outside_a_request_scope_still_composes():
    """No scope means no manifest and no dirtied keys, not an error."""
    assert compose("<p>hi</p>") == PjxResponse(body="<p>hi</p>", headers={})


class Greeting(BaseComponent):
    """A trivial component whose template renders one interpolated field."""

    name: str = ""


@pytest.fixture
def _greeting_template(tmp_path):
    """Publish a registry for Greeting and point it at a real template file."""
    template = tmp_path / "greeting.pjx"
    template.write_text("<p>{{ name }}</p>")
    discovery.build_registry(tmp_path, [Greeting])
    Greeting.__pjx_descriptor__ = dataclasses.replace(
        Greeting.__pjx_descriptor__, template_path=template
    )
    yield


def test_a_component_return_is_rendered_as_the_primary(_greeting_template):
    with request_scope():
        assert compose(Greeting(name="ada")).body == "<p>ada</p>"


def test_a_component_return_sets_no_reswap_header(_greeting_template):
    with request_scope():
        assert compose(Greeting(name="ada")).headers == {}
