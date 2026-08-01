"""Cold-render injection of the pjx.js runtime into a session's output."""

from __future__ import annotations

from typing import Any

from pyjinhx2.assets import AssetMode
from pyjinhx2.client import read_pjx_runtime, read_vendored_htmx
from pyjinhx2.session import RenderSession

PJX_MOUNTED_HEADER = "X-PJX-Mounted"


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
