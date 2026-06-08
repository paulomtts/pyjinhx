from pyjinhx import FastAPIClientBackend, Registry
from pyjinhx.reactive.backend import ClientBackend


class _FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


def test_client_backend_current_outside_scope_is_none():
    ClientBackend.reset()
    assert ClientBackend.current() is None


def test_client_backend_scope_sets_backend():
    request = _FakeRequest({"X-PJX-Mounted": "[]"})
    backend = FastAPIClientBackend(request)
    with ClientBackend.scope(backend):
        assert ClientBackend.current() is backend
    assert ClientBackend.current() is None


def test_fastapi_client_backend_reads_headers():
    request = _FakeRequest({"X-PJX-Mounted": "[]", "X-PJX-Assets": '["/a.js"]'})
    backend = FastAPIClientBackend(request)
    assert backend.get_header("X-PJX-Mounted") == "[]"
    assert backend.get_header("X-PJX-Assets") == '["/a.js"]'


def test_fastapi_client_backend_constructor():
    request = _FakeRequest({"X-PJX-Mounted": "[]"})
    backend = FastAPIClientBackend(request)
    assert isinstance(backend, FastAPIClientBackend)
    assert backend.get_header("X-PJX-Mounted") == "[]"


def test_registry_request_scope_sets_client_backend():
    request = _FakeRequest({"X-PJX-Mounted": "[]"})
    ClientBackend.reset()
    with Registry.request_scope(client_backend=FastAPIClientBackend(request)):
        current = ClientBackend.current()
        assert current is not None
        assert current.get_header("X-PJX-Mounted") == "[]"
    assert ClientBackend.current() is None


def test_registry_request_scope_with_fastapi_backend():
    request = _FakeRequest({"X-PJX-Mounted": "[]"})
    ClientBackend.reset()
    with Registry.request_scope(client_backend=FastAPIClientBackend(request)):
        assert ClientBackend.current() is not None
