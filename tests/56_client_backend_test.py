from pyjinhx import (
    PJX_MOUNTED_HEADER,
    FastAPIClientBackend,
    Registry,
    client_scope,
    fastapi_client_backend,
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


def test_fastapi_client_backend_reads_headers():
    backend = FastAPIClientBackend(_Request({PJX_MOUNTED_HEADER: "[]"}))
    assert backend.get_header(PJX_MOUNTED_HEADER) == "[]"
    assert backend.headers.get(PJX_MOUNTED_HEADER) == "[]"


def test_fastapi_client_backend_factory():
    request = _Request({"X-Test": "ok"})
    backend = fastapi_client_backend(request)
    assert backend.get_header("X-Test") == "ok"


def test_resolve_render_client_uses_backend():
    with client_scope(FastAPIClientBackend(_Request({}))):
        assert resolve_render_client(None) is not None
    assert resolve_render_client(None) is None


def test_resolve_render_mounted_mutation_only():
    manifest = "[]"
    with client_scope(FastAPIClientBackend(_Request({PJX_MOUNTED_HEADER: manifest}))):
        assert resolve_render_mounted(None, dirtied=None) is None
        assert resolve_render_mounted(None, dirtied={"todos"}) is not None
        with mutation_scope("todos"):
            pass
        assert resolve_render_mounted(None, dirtied=None) is not None


def test_request_scope_wires_client_backend():
    request = _Request({PJX_MOUNTED_HEADER: "[]"})
    with Registry.request_scope(client_backend=fastapi_client_backend(request)):
        client = resolve_render_client(None)
        assert client is not None
        assert client.headers.get(PJX_MOUNTED_HEADER) == "[]"
