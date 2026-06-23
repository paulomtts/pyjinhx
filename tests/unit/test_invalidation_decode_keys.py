import logging

from pyjinhx.cache import InvalidationBackend


class _StubBackend(InvalidationBackend):
    """Minimal concrete backend so we can exercise the shared ABC helper."""

    def publish(self, keys):  # pragma: no cover - not exercised here
        ...

    def start(self, handler):  # pragma: no cover
        ...

    def stop(self):  # pragma: no cover
        ...


def test_decode_keys_valid_list():
    assert _StubBackend()._decode_keys('["a", "b"]') == frozenset({"a", "b"})


def test_decode_keys_coerces_non_str_elements():
    assert _StubBackend()._decode_keys("[1, 2]") == frozenset({"1", "2"})


def test_decode_keys_bad_json_warns_and_returns_none(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        result = _StubBackend()._decode_keys("{not valid json")
    assert result is None
    assert any("Ignoring invalid invalidation payload" in r.message for r in caplog.records)


def test_decode_keys_non_list_returns_none():
    assert _StubBackend()._decode_keys("{}") is None
    assert _StubBackend()._decode_keys("5") is None


def test_default_channel_is_single_source():
    assert InvalidationBackend.DEFAULT_CHANNEL == "pyjinhx:invalidate"
