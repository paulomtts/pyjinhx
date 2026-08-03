"""The backend interface: what any framework adapter must provide to pyjinhx.

Route adaptation is deliberately absent. Turning a handler's pjx return into a
framework response is expressed here as to_response(), but *wiring* that onto
routes is not: FastAPI does it by swapping APIRoute subclasses and blanking
response_model, a Flask adapter would do it with an after_request hook, and a
bare-WSGI one with a decorator. Nothing useful survives generalising those, so
each backend owns its own wiring and the interface stays thin over the core
primitives in session.py that are already framework-agnostic.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

SETUP_FLAG = "pyjinhx_setup"
"""Attribute name a backend marks an app with once setup has been applied."""

ContextFactory = Callable[[Any], object | None]
"""Turns a backend's native request object into this request's load context."""


def load_context_for(request: object, factory: ContextFactory | None) -> object | None:
    """Return the load context for ``request``, or None when no factory is set.

    A backend passes the result to ``request_scope(load_context=...)``, which is
    what makes it readable from ``get_load_context()`` for the life of the
    request. An app with no factory configured is the normal case, not an error.
    """
    return factory(request) if factory is not None else None


@runtime_checkable
class IntegrationBackend(Protocol):
    """What a framework adapter implements so ``setup()`` can wire pyjinhx in.

    A backend binds one ``request_scope(load_context=...)`` per request around
    its handler - that primitive is already framework-agnostic, so it is a
    contract this interface states rather than a method it redeclares. The
    methods below are the parts that genuinely differ per framework.

    Calling these outside their lifecycle (``mount_static`` before setup,
    ``on_shutdown`` without a prior ``on_startup``) is undefined: this is an
    interface definition, not a hardened runtime, and backends are not required
    to guard it.
    """

    def is_installed(self, app: object) -> bool:
        """Whether setup has already been applied to ``app``.

        A backend's setup returns early when this is true, so a re-entrant
        setup cannot stack two scopes or two lifespans on one request.
        """
        ...

    def mark_installed(self, app: object) -> None:
        """Record that setup has been applied to ``app``."""
        ...

    def mount_static(self, app: object, directory: str) -> None:
        """Serve the files in ``directory`` at ``/static`` on ``app``."""
        ...

    def on_startup(self, app: object) -> None:
        """Run pyjinhx's configure step as ``app`` starts.

        Two plain hooks rather than one contextmanager: chaining around an app's
        own lifespan is an idiom each framework spells differently, so the
        interface fixes only the call points and leaves the chaining to the
        backend.
        """
        ...

    def on_shutdown(self, app: object) -> None:
        """Run pyjinhx's shutdown step as ``app`` stops."""
        ...

    def to_response(self, result: object, request: object | None) -> object:
        """Adapt a pjx handler return into this framework's response type.

        Non-pjx results pass through untouched, so a backend can call this on
        every handler return without inspecting it first.
        """
        ...
