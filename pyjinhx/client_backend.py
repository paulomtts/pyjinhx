from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_client_backend: ContextVar[ClientBackend | None] = ContextVar(
    "client_backend", default=None
)


class ClientBackend(ABC):
    """Framework-agnostic source for HTTP headers on the current request."""

    @abstractmethod
    def get_header(self, name: str) -> str | None: ...


class HeadersClientBackend(ClientBackend):
    """Read headers from a mapping (e.g. Starlette/FastAPI ``request.headers``)."""

    def __init__(self, headers: Mapping[str, str]) -> None:
        self._headers = headers

    def get_header(self, name: str) -> str | None:
        return self._headers.get(name)


class RequestClientBackend(HeadersClientBackend):
    """
    Default HTTP client backend for ASGI frameworks (FastAPI, Starlette).

    Wraps any request object that exposes ``.headers`` with ``.get(name)``.
    """

    def __init__(self, request: object) -> None:
        headers = getattr(request, "headers", None)
        if headers is None:
            raise TypeError(
                "RequestClientBackend requires a request with a .headers mapping"
            )
        super().__init__(headers)


def client_backend_from_request(request: object) -> RequestClientBackend:
    """Build the default client backend from an ASGI request (FastAPI/Starlette)."""
    return RequestClientBackend(request)


class _ClientHeaderProxy:
    """Duck-type ``.headers.get`` for ``parse_loaded_assets`` / ``_parse_mounted``."""

    def __init__(self, backend: ClientBackend) -> None:
        self._backend = backend

    class _Headers:
        def __init__(self, backend: ClientBackend) -> None:
            self._backend = backend

        def get(self, name: str, default: str | None = None) -> str | None:
            value = self._backend.get_header(name)
            return value if value is not None else default

    @property
    def headers(self) -> _Headers:
        return self._Headers(self._backend)


def get_client_backend() -> ClientBackend | None:
    return _client_backend.get()


def client_for_render() -> _ClientHeaderProxy | None:
    backend = get_client_backend()
    if backend is None:
        return None
    return _ClientHeaderProxy(backend)


def reset_client_backend_state() -> None:
    """Clear the request-scoped client backend. Mainly for tests."""
    _client_backend.set(None)


def resolve_render_client(explicit: object | None) -> object | None:
    if explicit is not None:
        return explicit
    return client_for_render()


def resolve_render_mounted(
    explicit: object | None,
    *,
    dirtied: object | None,
) -> object | None:
    if explicit is not None:
        return explicit
    from .mutations import pending_dirtied

    if dirtied is None and not pending_dirtied():
        return None
    return client_for_render()


@contextmanager
def client_scope(backend: ClientBackend | None) -> Generator[None, None, None]:
    token = _client_backend.set(backend)
    try:
        yield
    finally:
        _client_backend.reset(token)


class ClientBackendMiddleware:
    """
    Starlette/FastAPI ``BaseHTTPMiddleware`` helper: bind ``RequestClientBackend``
    for the request via ``Registry.request_scope``.

    Subclass or compose with your own middleware::

        class AppMiddleware(ClientBackendMiddleware, BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                return await self.bind_client_backend(request, call_next)
    """

    async def bind_client_backend(self, request: object, call_next: Any) -> Any:
        from .registry import Registry

        with Registry.request_scope(
            client_backend=client_backend_from_request(request),
        ):
            return await call_next(request)
