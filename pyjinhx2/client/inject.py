"""Cold-render injection of the pjx.js runtime, and pjx request header parsing."""

from __future__ import annotations

import json
import logging
from typing import Any

from pyjinhx2.assets import AssetMode
from pyjinhx2.client import read_pjx_runtime, read_vendored_htmx
from pyjinhx2.session import RenderSession

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
        OSError: If pjx.js or the vendored htmx source cannot be read.
    """
    if _is_mounted_request(request):
        return
    if session.runtime_injected:
        return
    if session.js_mode is not AssetMode.INLINE:
        return
    # htmx first, so window.htmx exists by the time pjx.js registers its
    # listeners; its own guard makes re-defining a page's htmx a no-op.
    session.runtime_script = (
        f"<script>{read_vendored_htmx()}{read_pjx_runtime()}</script>"
    )
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
                logger.warning("Could not parse %s as JSON; ignoring.", PJX_ASSETS_HEADER)
                return frozenset()
            if not isinstance(parsed, list):
                return frozenset()
            return frozenset(str(token) for token in parsed)  # pyright: ignore[reportUnknownVariableType]
        return LoadedAssets.parse(_header_value(client, PJX_ASSETS_HEADER))
