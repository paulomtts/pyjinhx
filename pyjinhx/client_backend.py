from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

_client_backend: ContextVar[ClientBackend | None] = ContextVar(
    "client_backend", default=None
)


class ClientBackend(ABC):
    """Framework-agnostic source for HTTP headers on the current request."""

    @abstractmethod
    def get_header(self, name: str) -> str | None: ...


class FastAPIClientBackend(ClientBackend):
    """
    Default client backend for FastAPI and Starlette.

    Wraps a request object's ``.headers`` mapping. The backend instance is also
    duck-typed for ``render()`` (``.headers.get``) without a separate proxy.
    """

    def __init__(self, request: object) -> None:
        headers = getattr(request, "headers", None)
        if headers is None:
            raise TypeError("FastAPIClientBackend requires request.headers")
        self.headers = headers

    def get_header(self, name: str) -> str | None:
        return self.headers.get(name)


def fastapi_client_backend(request: object) -> FastAPIClientBackend:
    """Build the default client backend from a FastAPI/Starlette request."""
    return FastAPIClientBackend(request)


def get_client_backend() -> ClientBackend | None:
    return _client_backend.get()


def reset_client_backend_state() -> None:
    """Clear the request-scoped client backend. Mainly for tests."""
    _client_backend.set(None)


def resolve_render_client(explicit: object | None) -> object | None:
    if explicit is not None:
        return explicit
    return get_client_backend()


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
    return get_client_backend()


@contextmanager
def client_scope(backend: ClientBackend | None) -> Generator[None, None, None]:
    token = _client_backend.set(backend)
    try:
        yield
    finally:
        _client_backend.reset(token)
