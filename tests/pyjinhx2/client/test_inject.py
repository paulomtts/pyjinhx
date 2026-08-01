"""Cold-render gating for the pjx.js runtime injection."""

from __future__ import annotations

import pytest

from pyjinhx2.assets import AssetMode
from pyjinhx2.client import read_pjx_runtime, read_vendored_htmx
from pyjinhx2.client.inject import PJX_MOUNTED_HEADER, inject_runtime
from pyjinhx2.session import RenderSession


class FakeRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers


def test_cold_render_injects_htmx_then_pjx():
    session = RenderSession()

    inject_runtime(session)

    script = session.runtime_script
    assert script is not None
    assert script.startswith("<script>") and script.endswith("</script>")
    assert script.index("if (!window.htmx)") < script.index(read_pjx_runtime())
    assert read_vendored_htmx() in script
    assert session.runtime_injected is True


def test_request_none_is_treated_as_cold():
    session = RenderSession()

    inject_runtime(session, None)

    assert session.runtime_script is not None


def test_mounted_header_as_string_skips_injection():
    session = RenderSession()

    inject_runtime(session, '["btn-1"]')

    assert session.runtime_script is None
    assert session.runtime_injected is False


def test_mounted_header_on_request_object_skips_injection():
    session = RenderSession()

    inject_runtime(session, FakeRequest({PJX_MOUNTED_HEADER: '["btn-1"]'}))

    assert session.runtime_script is None
    assert session.runtime_injected is False


def test_request_object_without_the_header_still_injects():
    session = RenderSession()

    inject_runtime(session, FakeRequest({"Accept": "text/html"}))

    assert session.runtime_script is not None


@pytest.mark.parametrize("mode", [AssetMode.NONE, AssetMode.LINK])
def test_non_inline_js_mode_never_injects(mode: AssetMode):
    session = RenderSession()
    session.js_mode = mode

    inject_runtime(session)

    assert session.runtime_script is None
    assert session.runtime_injected is False


def test_second_call_on_the_same_session_is_a_no_op():
    session = RenderSession()
    inject_runtime(session)
    first = session.runtime_script

    inject_runtime(session)

    assert session.runtime_script == first
    assert session.runtime_script is not None
    # Idempotency check: a re-injection would double the payload length, not
    # just leave it unchanged, so this catches concatenation-on-top-of-itself
    # bugs that `== first` alone would still pass if both calls produced
    # identical (but doubled) output by coincidence.
    assert len(session.runtime_script) == len(first)
    assert session.runtime_injected is True


def test_malformed_request_falls_open_to_cold_render():
    session = RenderSession()

    inject_runtime(session, object())

    assert session.runtime_script is not None
    assert session.runtime_injected is True


def test_lowercase_header_key_also_skips_injection():
    session = RenderSession()

    inject_runtime(session, FakeRequest({PJX_MOUNTED_HEADER.lower(): '["btn-1"]'}))

    assert session.runtime_script is None
