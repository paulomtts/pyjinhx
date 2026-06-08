from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import ClassVar


class ClientBackend(ABC):
    """Framework-agnostic source for HTTP headers on the current request."""

    _context: ClassVar[ContextVar[ClientBackend | None]] = ContextVar(
        "client_backend", default=None
    )

    @abstractmethod
    def get_header(self, name: str) -> str | None: ...

    @classmethod
    def current(cls) -> ClientBackend | None:
        return cls._context.get()

    @classmethod
    def reset(cls) -> None:
        """Clear the request-scoped client backend. Mainly for tests."""
        cls._context.set(None)

    @classmethod
    @contextmanager
    def scope(cls, backend: ClientBackend | None) -> Generator[None, None, None]:
        token = cls._context.set(backend)
        try:
            yield
        finally:
            cls._context.reset(token)

    @classmethod
    def resolve_client(cls, explicit: object | None) -> object | None:
        if explicit is not None:
            return explicit
        return cls.current()

    @classmethod
    def resolve_mounted(
        cls,
        explicit: object | None,
        *,
        dirtied: object | None,
    ) -> object | None:
        if explicit is not None:
            return explicit
        from .mutations import pending_dirtied

        if dirtied is None and not pending_dirtied():
            return None
        return cls.current()


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
