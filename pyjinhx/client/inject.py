"""Cold-render injection of the pjx.js runtime, and pjx request header parsing."""

from __future__ import annotations

import json
import logging
from typing import Any

from pyjinhx.assets import AssetMode
from pyjinhx.client import (
    read_loading_indicator_js,
    read_page_loader_js,
    read_pjx_runtime,
    read_pjx_style_css,
    read_vendored_htmx,
)
from pyjinhx.session import RenderSession

logger = logging.getLogger(__name__)

PJX_MOUNTED_HEADER = "X-PJX-Mounted"
"""Header carrying the client's mounted-region manifest."""

PJX_TRIGGER_HEADER = "X-PJX-Trigger"
"""Header carrying the data-pjx-id of the element that started the request."""

PJX_ASSETS_HEADER = "X-PJX-Assets"
"""Header carrying the client's already-loaded asset token set."""


def _header_value(source: Any, name: str) -> str | None:
    """Read header *name* off a request-like *source*, or None if unavailable.

    Checks the exact name then the lowercase one: a real ASGI request's
    headers are case-insensitive, but a plain dict from a test or a
    hand-rolled client is not.
    """
    headers = getattr(source, "headers", None)
    if headers is None:
        return None
    try:
        value = headers.get(name)
        if value is None:
            value = headers.get(name.lower())
    except AttributeError:
        return None
    return value


def _is_mounted_request(request: Any) -> bool:
    """Whether the request says the browser already has the runtime loaded.

    Presence only — the header's payload is parsed elsewhere. Accepts the
    header value directly, anything with a ``.headers`` mapping, or None, and
    anything else counts as not mounted: falling open means a page that would
    otherwise ship no runtime at all, which is the recoverable direction.
    """
    if request is None:
        return False
    if isinstance(request, str):
        return bool(request)
    headers = getattr(request, "headers", None)
    if headers is None:
        return False
    try:
        value = headers.get(PJX_MOUNTED_HEADER)
        if value is None:
            # A real ASGI request's headers are case-insensitive; a plain dict
            # in a test or a hand-rolled client is not.
            value = headers.get(PJX_MOUNTED_HEADER.lower())
    except AttributeError:
        return False
    return value is not None


def inject_runtime(session: RenderSession, request: Any = None) -> None:
    """Record the inline pjx.js runtime on ``session`` for a cold render.

    No-ops when the request already carries the mounted header, when this
    session was injected once already, or when JS is not delivered inline.

    Args:
        session: The RenderSession this render writes into.
        request: The incoming request, its ``X-PJX-Mounted`` header value, or
            None outside a request.

    Raises:
        OSError: If pjx.js, the vendored htmx source, or a loading artifact
            cannot be read.
    """
    if _is_mounted_request(request):
        return
    if session.runtime_injected:
        return
    if session.js_mode is not AssetMode.INLINE:
        return
    # htmx first, so window.htmx exists by the time pjx.js registers its
    # listeners; its own guard makes re-defining a page's htmx a no-op. The two
    # loading artifacts come last: they call pjx.region/pjx.loadingTargets.
    session.runtime_script = (
        f"<script>{read_vendored_htmx()}{read_pjx_runtime()}"
        f"{read_loading_indicator_js()}{read_page_loader_js()}</script>"
    )
    session.runtime_style = f'<style id="pjx-style">{read_pjx_style_css()}</style>'
    session.runtime_injected = True


class LoadedAssets:
    """Parser for the ``X-PJX-Assets`` header."""

    @staticmethod
    def parse(client: str | list[str] | object | None) -> frozenset[str]:
        """Return the asset tokens the browser reports it already has.

        Accepts a raw header string, a pre-parsed list, a request-like object,
        or None. Anything unreadable yields an empty set: re-sending an asset
        the client already has is wasteful but harmless, while raising on a
        browser-supplied header would take the whole response down.
        """
        if client is None or client == "":
            return frozenset()
        if isinstance(client, list):
            return frozenset(str(token) for token in client)
        if isinstance(client, str):
            try:
                parsed = json.loads(client)
            except json.JSONDecodeError:
                logger.warning(
                    "Could not parse %s as JSON; ignoring.", PJX_ASSETS_HEADER
                )
                return frozenset()
            if not isinstance(parsed, list):
                return frozenset()
            return frozenset(str(token) for token in parsed)  # pyright: ignore[reportUnknownVariableType]
        return LoadedAssets.parse(_header_value(client, PJX_ASSETS_HEADER))


class MountedManifest:
    """Parser for the ``X-PJX-Mounted`` header."""

    @staticmethod
    def parse(
        mounted: str | list[dict[str, Any]] | object | None,
    ) -> list[dict[str, Any]]:
        """Return the regions the browser reports it currently has mounted.

        Each entry is ``{id, type, load, hash}``. Accepts a raw header string,
        a pre-parsed list, a request-like object, or None. Anything unreadable
        yields an empty list, which downstream fanout reads as "nothing is
        mounted" — a full render rather than a failed one.
        """
        if mounted is None or mounted == "":
            return []
        if isinstance(mounted, list):
            return mounted
        if isinstance(mounted, str):
            try:
                parsed = json.loads(mounted)
            except json.JSONDecodeError:
                logger.warning(
                    "Could not parse %s as JSON; ignoring.", PJX_MOUNTED_HEADER
                )
                return []
            return parsed if isinstance(parsed, list) else []
        return MountedManifest.parse(_header_value(mounted, PJX_MOUNTED_HEADER))


class TriggerManifest:
    """Parser for the ``X-PJX-Trigger`` header."""

    @staticmethod
    def parse(client: str | dict[str, Any] | object | None) -> dict[str, Any] | None:
        """Return the descriptor of the element that started the request.

        Accepts a raw header string, a pre-parsed dict, a request-like object,
        or None. A descriptor without a truthy ``id`` is useless to callers
        that key off it, so it collapses to None rather than a half-empty dict.
        """
        if client is None or client == "":
            return None
        if isinstance(client, dict):
            return client if client.get("id") else None  # pyright: ignore[reportUnknownArgumentType]
        if isinstance(client, str):
            try:
                parsed = json.loads(client)
            except json.JSONDecodeError:
                logger.warning(
                    "Could not parse %s as JSON; ignoring.", PJX_TRIGGER_HEADER
                )
                return None
            return parsed if isinstance(parsed, dict) and parsed.get("id") else None
        return TriggerManifest.parse(_header_value(client, PJX_TRIGGER_HEADER))
