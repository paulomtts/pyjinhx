import json

from pyjinhx import (
    PJX_MOUNTED_HEADER,
    Registry,
    RequestClientBackend,
    client_backend_from_request,
    client_for_render,
    client_scope,
)
from pyjinhx.client_backend import resolve_render_client, resolve_render_mounted
from pyjinhx.mutations import mutation_scope


class _Headers:
    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._mapping.get(name, default)


class _Request:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = _Headers(headers)


def test_request_client_backend_reads_headers():
    backend = RequestClientBackend(_Request({PJX_MOUNTED_HEADER: "[]"}))
    assert backend.get_header(PJX_MOUNTED_HEADER) == "[]"


def test_client_backend_from_request():
    request = _Request({"X-Test": "ok"})
    backend = client_backend_from_request(request)
    assert backend.get_header("X-Test") == "ok"


def test_client_for_render_proxy():
    manifest = json.dumps([{"id": "c", "type": "Counter", "hash": "x"}])
    with client_scope(RequestClientBackend(_Request({PJX_MOUNTED_HEADER: manifest}))):
        proxy = client_for_render()
        assert proxy is not None
        assert proxy.headers.get(PJX_MOUNTED_HEADER) == manifest


def test_resolve_render_client_uses_backend():
    with client_scope(RequestClientBackend(_Request({}))):
        assert resolve_render_client(None) is not None
    assert resolve_render_client(None) is None


def test_resolve_render_mounted_mutation_only():
    manifest = "[]"
    with client_scope(RequestClientBackend(_Request({PJX_MOUNTED_HEADER: manifest}))):
        assert resolve_render_mounted(None, dirtied=None) is None
        assert resolve_render_mounted(None, dirtied={"todos"}) is not None
        with mutation_scope("todos"):
            pass
        assert resolve_render_mounted(None, dirtied=None) is not None


def test_request_scope_wires_client_backend():
    request = _Request({PJX_MOUNTED_HEADER: "[]"})
    with Registry.request_scope(client_backend=client_backend_from_request(request)):
        assert resolve_render_client(None) is not None
        assert resolve_render_client(None).headers.get(PJX_MOUNTED_HEADER) == "[]"
