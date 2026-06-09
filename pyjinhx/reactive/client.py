"""Client backend, manifest parsers, and runtime script injection for pyjinhx."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, ClassVar

from markupsafe import Markup

from pyjinhx.core.assets import DEFAULT_RUNTIME_URL, AssetMode
from pyjinhx.core.renderer import Renderer
from pyjinhx.utils import read_client_runtime

logger = logging.getLogger("pyjinhx")


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

PJX_ASSETS_HEADER = "X-PJX-Assets"
"""Name of the HTTP header carrying asset URLs already loaded in the browser."""

PJX_TRIGGER_HEADER = "X-PJX-Trigger"
"""Name of the HTTP header carrying the data-pjx-id of the element that started the request."""


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


class LoadedAssets:
    @staticmethod
    def parse(client: str | list[str] | object | None) -> frozenset[str]:
        if client is None or client == "":
            return frozenset()
        if isinstance(client, (list, tuple, set, frozenset)):
            return frozenset(str(url) for url in client)
        if isinstance(client, str):
            try:
                parsed = json.loads(client)
            except json.JSONDecodeError:
                logger.warning("Could not parse %s as JSON; ignoring.", PJX_ASSETS_HEADER)
                return frozenset()
            return frozenset(str(url) for url in parsed) if isinstance(parsed, list) else frozenset()
        try:
            header_value = client.headers.get(PJX_ASSETS_HEADER)  # type: ignore[attr-defined]
        except AttributeError:
            return frozenset()
        return LoadedAssets.parse(header_value)


def client_script(
    *,
    mode: AssetMode | None = None,
    src: str | None = None,
) -> Markup:
    """
    Return the pyjinhx client runtime as a ``<script>`` tag.

    Drop this into a raw Jinja page shell when you are not rendering through a
    root ``BaseComponent.render()`` call. Root full-page renders inject the
    runtime automatically unless the request already carries ``X-PJX-Mounted``.

    Args:
        mode: ``AssetMode.INLINE`` (default) inlines the runtime source.
            ``AssetMode.REFERENCE`` emits ``<script src="...">``.
        src: Public URL for the runtime when ``mode`` is ``AssetMode.REFERENCE``.
            Defaults to ``Renderer``'s configured runtime URL.
    """
    effective_mode = mode or AssetMode.INLINE
    if effective_mode == AssetMode.REFERENCE:
        runtime_url = src or Renderer._default_runtime_url or DEFAULT_RUNTIME_URL
        return Markup(f'<script src="{runtime_url}"></script>')
    return Markup(f"<script>{read_client_runtime()}</script>")
