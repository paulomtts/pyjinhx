"""The framework-free response layer: what one handler return becomes.

Every backend funnels its handler returns through this module and does nothing
with them but emit the result. Fan-out and the htmx header set live here so no
two backends can disagree about them.
"""

from __future__ import annotations

from dataclasses import dataclass

from markupsafe import Markup

from pyjinhx._component import BaseComponent
from pyjinhx.reactive.assets import missing_asset_oob
from pyjinhx.reactive.cache import invalidate
from pyjinhx.reactive.fanout import oob_swaps, walk_manifest
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession, current_session, get_dirtied


@dataclass(frozen=True)
class PjxResponse:
    """One composed response, in terms no web framework has to be installed for.

    A backend's whole remaining job is turning this into its own response type.
    """

    body: str
    headers: dict[str, str]
    status: int = 200


PASSTHROUGH = object()
"""``compose()``'s answer for a return value that is not pyjinhx's to adapt."""


def _fan_out(primary: str, session: RenderSession) -> tuple[str, dict[str, str]]:
    """The whole body and htmx headers for a primary, with the OOB legs attached.

    Args:
        primary: This request's already-serialized primary markup, possibly empty.
        session: The session carrying the client's manifest and asset tokens.

    Returns:
        The joined body and the htmx headers the body itself implies.
    """
    dirtied = get_dirtied()
    # Evict before walking, never after: walk_manifest reads the load cache to
    # decide clean vs dirty, so an entry a dirtied key already stale-ed would
    # otherwise answer "clean" and the client would keep markup this request
    # just invalidated.
    invalidate(dirtied)
    # primary_html is passed so a region the primary body already carries is not
    # also swapped OOB: fan-out runs after the primary serialize, and without
    # this the client would swap that region twice in one response.
    candidates = walk_manifest(
        session.pjx_mounted, dirtied, session=session, primary_html=primary
    )
    parts = [
        primary,
        str(oob_swaps(candidates)),
        missing_asset_oob(candidates, session.pjx_assets, session),
    ]
    # An OOB-only body has nothing for htmx's default swap to place, so htmx would
    # swap the empty primary into the triggering element and wipe it. Telling htmx
    # not to swap at all leaves the trigger alone and lets the OOB fragments land.
    headers = {} if primary.strip() else {"HX-Reswap": "none"}
    return "\n".join(part for part in parts if part), headers


def compose(result: object, *, session: RenderSession | None = None) -> object:
    """Turn one handler return into a PjxResponse, or answer PASSTHROUGH.

    Fan-out is attached on every path that produces a body, because the dirtied
    keys belong to the request rather than to whatever the handler chose to
    return: a mutation that dirtied `todos` did so no matter which of the
    equivalent spellings the author reached for.

    Args:
        result: Whatever the handler returned.
        session: The session to compose against. Defaults to the active
            ``request_scope()``'s, and to a bare one outside a scope.

    Returns:
        A ``PjxResponse``, or ``PASSTHROUGH`` when ``result`` is not a pyjinhx
        return type and the backend should keep its own value. A framework's own
        response object takes that second path, which is how a handler's
        redirect survives to reach the backend's translation step.
    """
    session = session or current_session() or RenderSession()
    if isinstance(result, BaseComponent):
        primary = render(result, session=session)
    elif result is None:
        primary = ""
    elif isinstance(result, str) or hasattr(result, "__html__"):
        # Markup() rather than str(): a handler-supplied primary can be an object
        # exposing only __html__ and never __str__, and Markup is what adopts
        # that protocol without escaping. str()-ing it first would fall through
        # to object.__str__ and ship a Python repr instead of the markup.
        primary = str(Markup(result))
    else:
        return PASSTHROUGH
    body, headers = _fan_out(primary, session)
    return PjxResponse(body=body, headers=headers)
