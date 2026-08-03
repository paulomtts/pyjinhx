"""Cold-render gating for the pjx.js runtime injection."""

from __future__ import annotations

import json
import logging

import pytest

from pyjinhx.assets import AssetMode
from pyjinhx.client import (
    read_loading_indicator_js,
    read_page_loader_js,
    read_pjx_runtime,
    read_pjx_style_css,
    read_vendored_htmx,
)
from pyjinhx.client.inject import PJX_MOUNTED_HEADER, inject_runtime
from pyjinhx.session import RenderSession


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


def test_cold_render_bundles_the_loading_artifacts_into_the_same_script():
    session = RenderSession()

    inject_runtime(session)

    script = session.runtime_script
    assert script is not None
    assert script.startswith("<script>") and script.endswith("</script>")
    assert read_loading_indicator_js() in script
    assert read_page_loader_js() in script
    assert script.index(read_pjx_runtime()) < script.index(read_loading_indicator_js())


def test_cold_render_emits_the_pjx_style_block():
    session = RenderSession()

    inject_runtime(session)

    style = session.runtime_style
    assert style is not None
    assert style.startswith('<style id="pjx-style">') and style.endswith("</style>")
    assert read_pjx_style_css() in style


def test_runtime_style_survives_a_non_inline_css_mode():
    from pyjinhx.assets import emit_assets

    session = RenderSession()
    session.css_mode = AssetMode.LINK

    inject_runtime(session)

    assert session.runtime_style is not None
    assert session.runtime_style in emit_assets(session, resolver=lambda p: str(p))


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
    assert first is not None
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


def test_header_constants_match_the_wire_names():
    from pyjinhx.client.inject import PJX_ASSETS_HEADER, PJX_TRIGGER_HEADER

    assert PJX_TRIGGER_HEADER == "X-PJX-Trigger"
    assert PJX_ASSETS_HEADER == "X-PJX-Assets"


def test_header_value_finds_exact_and_lowercase_keys():
    from pyjinhx.client.inject import PJX_ASSETS_HEADER, _header_value

    exact = FakeRequest({PJX_ASSETS_HEADER: '["a"]'})
    lower = FakeRequest({PJX_ASSETS_HEADER.lower(): '["a"]'})

    assert _header_value(exact, PJX_ASSETS_HEADER) == '["a"]'
    assert _header_value(lower, PJX_ASSETS_HEADER) == '["a"]'


def test_header_value_returns_none_for_unusable_sources():
    from pyjinhx.client.inject import PJX_ASSETS_HEADER, _header_value

    assert (
        _header_value(FakeRequest({"Accept": "text/html"}), PJX_ASSETS_HEADER) is None
    )
    assert _header_value(object(), PJX_ASSETS_HEADER) is None
    assert _header_value(None, PJX_ASSETS_HEADER) is None


def test_loaded_assets_parses_a_json_string_list():
    from pyjinhx.client.inject import LoadedAssets

    assert LoadedAssets.parse('["card.css", "chart.js"]') == frozenset(
        {"card.css", "chart.js"}
    )


def test_loaded_assets_accepts_a_pre_parsed_list():
    from pyjinhx.client.inject import LoadedAssets

    assert LoadedAssets.parse(["card.css", "card.css"]) == frozenset({"card.css"})


def test_loaded_assets_reads_the_header_off_a_request():
    from pyjinhx.client.inject import PJX_ASSETS_HEADER, LoadedAssets

    exact = FakeRequest({PJX_ASSETS_HEADER: '["card.css"]'})
    lower = FakeRequest({PJX_ASSETS_HEADER.lower(): '["card.css"]'})

    assert LoadedAssets.parse(exact) == frozenset({"card.css"})
    assert LoadedAssets.parse(lower) == frozenset({"card.css"})


@pytest.mark.parametrize(
    "client",
    [None, "", FakeRequest({"Accept": "text/html"}), object(), '{"a": 1}', "[]"],
)
def test_loaded_assets_empty_inputs_yield_an_empty_frozenset(client: object):
    from pyjinhx.client.inject import LoadedAssets

    assert LoadedAssets.parse(client) == frozenset()


def test_loaded_assets_warns_and_falls_open_on_malformed_json(caplog):
    from pyjinhx.client.inject import PJX_ASSETS_HEADER, LoadedAssets

    with caplog.at_level(logging.WARNING, logger="pyjinhx.client.inject"):
        assert LoadedAssets.parse("not json") == frozenset()

    assert PJX_ASSETS_HEADER in caplog.text


MANIFEST_ENTRY = {
    "id": "card-1",
    "type": "Card",
    "load": "eager",
    "hash": "abc123",
}


def test_mounted_manifest_parses_a_json_string_and_keeps_every_field():
    from pyjinhx.client.inject import MountedManifest

    parsed = MountedManifest.parse(json.dumps([MANIFEST_ENTRY]))

    assert parsed == [MANIFEST_ENTRY]
    assert set(parsed[0]) == {"id", "type", "load", "hash"}


def test_mounted_manifest_accepts_a_pre_parsed_list():
    from pyjinhx.client.inject import MountedManifest

    assert MountedManifest.parse([MANIFEST_ENTRY]) == [MANIFEST_ENTRY]


def test_mounted_manifest_reads_the_header_off_a_request():
    from pyjinhx.client.inject import PJX_MOUNTED_HEADER, MountedManifest

    payload = json.dumps([MANIFEST_ENTRY])
    exact = FakeRequest({PJX_MOUNTED_HEADER: payload})
    lower = FakeRequest({PJX_MOUNTED_HEADER.lower(): payload})

    assert MountedManifest.parse(exact) == [MANIFEST_ENTRY]
    assert MountedManifest.parse(lower) == [MANIFEST_ENTRY]


@pytest.mark.parametrize(
    "mounted",
    [None, "", FakeRequest({"Accept": "text/html"}), object(), '{"id": "card-1"}'],
)
def test_mounted_manifest_empty_inputs_yield_an_empty_list(mounted: object):
    from pyjinhx.client.inject import MountedManifest

    assert MountedManifest.parse(mounted) == []


def test_mounted_manifest_warns_and_falls_open_on_malformed_json(caplog):
    from pyjinhx.client.inject import PJX_MOUNTED_HEADER, MountedManifest

    with caplog.at_level(logging.WARNING, logger="pyjinhx.client.inject"):
        assert MountedManifest.parse("not json") == []

    assert PJX_MOUNTED_HEADER in caplog.text


TRIGGER = {"id": "btn-1", "type": "Button"}


def test_trigger_manifest_parses_a_json_string_with_a_truthy_id():
    from pyjinhx.client.inject import TriggerManifest

    assert TriggerManifest.parse(json.dumps(TRIGGER)) == TRIGGER


def test_trigger_manifest_accepts_a_pre_parsed_dict():
    from pyjinhx.client.inject import TriggerManifest

    assert TriggerManifest.parse(dict(TRIGGER)) == TRIGGER


def test_trigger_manifest_reads_the_header_off_a_request():
    from pyjinhx.client.inject import PJX_TRIGGER_HEADER, TriggerManifest

    payload = json.dumps(TRIGGER)
    exact = FakeRequest({PJX_TRIGGER_HEADER: payload})
    lower = FakeRequest({PJX_TRIGGER_HEADER.lower(): payload})

    assert TriggerManifest.parse(exact) == TRIGGER
    assert TriggerManifest.parse(lower) == TRIGGER


@pytest.mark.parametrize(
    "client",
    [
        None,
        "",
        FakeRequest({"Accept": "text/html"}),
        object(),
        '{"type": "Button"}',
        '{"id": ""}',
        {"id": ""},
        "[1, 2]",
    ],
)
def test_trigger_manifest_without_a_truthy_id_is_none(client: object):
    from pyjinhx.client.inject import TriggerManifest

    assert TriggerManifest.parse(client) is None


def test_trigger_manifest_warns_and_falls_open_on_malformed_json(caplog):
    from pyjinhx.client.inject import PJX_TRIGGER_HEADER, TriggerManifest

    with caplog.at_level(logging.WARNING, logger="pyjinhx.client.inject"):
        assert TriggerManifest.parse("not json") is None

    assert PJX_TRIGGER_HEADER in caplog.text
