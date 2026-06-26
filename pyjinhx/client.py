"""Client backend, manifest parsers, and runtime script injection for pyjinhx."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, ClassVar

from markupsafe import Markup

from pyjinhx.utils import read_client_runtime

logger = logging.getLogger("pyjinhx")


@dataclass
class ResponseDirectives:
    """Per-request directives the integration applies to the outgoing response.

    Set on the request scope, mutated during the request (e.g. by
    ``ReactiveResponse``), and read by the integration when finalizing the
    response. Framework-agnostic: ``headers()`` is the wire form.
    """

    reswap_none: bool = False

    def headers(self) -> dict[str, str]:
        """The ``HX-*`` response headers implied by these directives."""
        return {"HX-Reswap": "none"} if self.reswap_none else {}


_response_directives: ContextVar[ResponseDirectives | None] = ContextVar(
    "pjx_response_directives", default=None
)


def current_directives() -> ResponseDirectives | None:
    """This request's :class:`ResponseDirectives`, or ``None`` outside a request scope."""
    return _response_directives.get()


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
    def resolve_client(cls, explicit: object | None = None) -> object | None:
        if explicit is not None:
            return explicit
        return cls.current()


PJX_MOUNTED_HEADER = "X-PJX-Mounted"
"""Name of the HTTP header carrying the client's mounted-region manifest."""

PJX_TRIGGER_HEADER = "X-PJX-Trigger"
"""Name of the HTTP header carrying the data-pjx-id of the element that started the request."""

PJX_ASSETS_HEADER = "X-PJX-Assets"
"""Name of the HTTP header carrying the client's already-loaded asset token set."""


class LoadedAssets:
    @staticmethod
    def parse(client: str | list[str] | object | None) -> frozenset[str]:
        """
        Parse ``X-PJX-Assets`` off *client* and return a frozenset of token strings.

        *client* may be a raw JSON string, a pre-parsed list, a request-like
        object with a ``.headers`` mapping, or ``None`` / empty string — all
        yield an empty frozenset gracefully.
        """
        if client is None or client == "":
            return frozenset()
        if isinstance(client, list):
            return frozenset(str(t) for t in client)
        if isinstance(client, str):
            try:
                parsed = json.loads(client)
            except json.JSONDecodeError:
                logger.warning(
                    "Could not parse %s as JSON; ignoring.", PJX_ASSETS_HEADER
                )
                return frozenset()
            if isinstance(parsed, list):
                return frozenset(str(t) for t in parsed)
            return frozenset()
        try:
            header_value = client.headers.get(PJX_ASSETS_HEADER)  # type: ignore[attr-defined]
        except AttributeError:
            return frozenset()
        return LoadedAssets.parse(header_value)


class MountedManifest:
    @staticmethod
    def parse(
        mounted: str | list[dict[str, Any]] | object | None,
    ) -> list[dict[str, Any]]:
        if mounted is None or mounted == "":
            return []
        if isinstance(mounted, list):
            return mounted
        if isinstance(mounted, str):
            try:
                parsed = json.loads(mounted)
            except json.JSONDecodeError:
                logger.warning("Could not parse %s as JSON; ignoring.", PJX_MOUNTED_HEADER)
                return []
            return parsed if isinstance(parsed, list) else []
        try:
            header_value = mounted.headers.get(PJX_MOUNTED_HEADER)  # type: ignore[attr-defined]
        except AttributeError:
            logger.warning(
                "mounted is not an %s header string, parsed list, request-like "
                "object, or None; ignoring.",
                PJX_MOUNTED_HEADER,
            )
            return []
        return MountedManifest.parse(header_value)

    @staticmethod
    def is_present(client: str | list[dict[str, Any]] | object | None) -> bool:
        if client is None:
            return False
        if isinstance(client, list):
            return True
        if isinstance(client, str):
            if client == "":
                return False
            try:
                parsed = json.loads(client)
            except json.JSONDecodeError:
                return False
            return isinstance(parsed, list)
        try:
            header_value = client.headers.get(PJX_MOUNTED_HEADER)  # type: ignore[attr-defined]
        except AttributeError:
            return False
        return MountedManifest.is_present(header_value)


class TriggerManifest:
    @staticmethod
    def parse(client: str | dict[str, Any] | object | None) -> dict[str, Any] | None:
        if client is None or client == "":
            return None
        if isinstance(client, str):
            try:
                parsed = json.loads(client)
            except json.JSONDecodeError:
                logger.warning("Could not parse %s as JSON; ignoring.", PJX_TRIGGER_HEADER)
                return None
            return parsed if isinstance(parsed, dict) and parsed.get("id") else None
        try:
            header_value = client.headers.get(PJX_TRIGGER_HEADER)  # type: ignore[attr-defined]
        except AttributeError:
            return None
        return TriggerManifest.parse(header_value)


def client_script() -> Markup:
    """
    Return the pyjinhx client runtime as an inline ``<script>`` tag.

    Drop this into a raw Jinja page shell when you are not rendering through a
    root ``BaseComponent.render()`` call. Root full-page renders inject the
    runtime automatically unless the request already carries ``X-PJX-Mounted``.
    """
    return Markup(f"<script>{read_client_runtime()}</script>")
