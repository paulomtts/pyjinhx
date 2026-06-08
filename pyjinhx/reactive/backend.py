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
        from .mutations import MutationTracker

        if dirtied is None and not MutationTracker.pending():
            return None
        return cls.current()
