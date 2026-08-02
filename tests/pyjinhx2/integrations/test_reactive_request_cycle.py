"""One live FastAPI request cycle: config, middleware, context and dev together.

Unlike the per-module tests, nothing here enters ``request_scope()`` by hand or
builds a fake request: every assertion is made on an HTTP response TestClient
returned, or on state read from inside a handler the middleware called.
"""

import dataclasses
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from pyjinhx2 import discovery, registry
from pyjinhx2.config import PjxSettings
from pyjinhx2.context import PjxContext
from pyjinhx2.integrations.fastapi import apply_setup
from pyjinhx2.reactive.cache import invalidate
from pyjinhx2.reactive.component import PjxKey, ReactiveComponent
from pyjinhx2.reactive.keys import MutationKey
from pyjinhx2.reactive.mutations import dirty, mutates
from pyjinhx2.reactive.response import ReactiveResponse
from pyjinhx2.session import (
    NoActiveRequestScope,
    current_session,
    get_dirtied,
)

STORE: dict[str, int] = {}
"""The app-level state CycleCard.load() reads, standing in for a database."""

LOAD_CALLS: list[str] = []
"""One entry per real (uncached) load() body run, for cache-hit assertions."""


class Keys(MutationKey):
    """The reactive keys this module's tests dirty.

    ``dirty()``/``@mutates`` reject a bare string (see
    ``tests/pyjinhx2/reactive/test_reactive_mutations.py::test_mutates_rejects_a_plain_string``
    on origin/master) — every key has to be a ``MutationKey`` member or a
    ``reactive_key()`` value, so a plain ``"cycle"`` literal would raise
    ``TypeError`` at class-body/call time instead of dirtying anything.
    """

    CYCLE = "cycle"
    ORPHAN = "nobody-reads-this"


class CycleCard(ReactiveComponent, react=(Keys.CYCLE,)):
    """A reactive card keyed by ``pjx_key``, dirtied by the ``cycle`` key."""

    pjx_key: Annotated[str, PjxKey()] = ""

    def load(self) -> int:
        LOAD_CALLS.append(self.pjx_key)
        return STORE.get(self.pjx_key, 0)


class Counter:
    """An app object whose mutation method dirties the ``cycle`` key."""

    @mutates(Keys.CYCLE)
    def bump(self, card_id: str) -> None:
        STORE[card_id] = STORE.get(card_id, 0) + 1


@pytest.fixture(autouse=True)
def _publish_registry():
    """Publish the tag -> class map and reset the per-test app state."""
    STORE.clear()
    LOAD_CALLS.clear()
    template_dir = Path(__file__).parent.parent.parent / "templates"
    discovery.build_registry(template_dir, [CycleCard])
    # `_resolve_template_path` probes the class's *defining module* directory
    # (this test file's), not the dir handed to build_registry, so the
    # descriptor is repointed at the bare template name the middleware's
    # FileSystemLoader will join under tests/templates.
    CycleCard.__pjx_descriptor__ = dataclasses.replace(
        CycleCard.__pjx_descriptor__, template_path=Path("cycle_card.pjx")
    )
    yield


def make_app(**settings_kwargs) -> FastAPI:
    """A FastAPI app with pyjinhx2 wired in through apply_setup()."""
    app = FastAPI()
    apply_setup(app, PjxSettings(**settings_kwargs))
    return app


def entry(instance_id: str, load: object, hash_: str = "stale") -> dict:
    """One synthetic X-PJX-Mounted entry naming a mounted CycleCard region."""
    return {"type": "cycle_card", "id": instance_id, "load": load, "hash": hash_}


def test_apply_setup_idempotent_on_repeat_calls():
    app = make_app()
    apply_setup(app, PjxSettings())
    apply_setup(app, PjxSettings())

    names = [
        middleware.cls.__name__  # pyright: ignore[reportAttributeAccessIssue]
        for middleware in app.user_middleware
    ]
    assert names.count("PjxScopeMiddleware") == 1
    assert app.state.pyjinhx_setup is True

    @app.get("/ping")
    def ping():
        return {"scopes": current_session() is not None}

    with TestClient(app) as client:
        assert client.get("/ping").json() == {"scopes": True}


def test_request_scope_contextvars_reset_after_response():
    app = make_app()
    seen: list[dict[str, object]] = []

    @app.post("/dirty")
    def dirty_endpoint(request: Request):
        dirty(Keys.CYCLE)
        seen.append(
            {
                "session": current_session(),
                "dirtied": set(get_dirtied()),
                "mounted": request.state.pjx_mounted,
            }
        )
        return {"ok": True}

    with TestClient(app) as client:
        client.post("/dirty", headers={"X-PJX-Mounted": '[{"id": "a"}]'})
        client.post("/dirty")

    first, second = seen
    assert first["dirtied"] == {"cycle"}
    # A fresh dirtied set per request: the second request sees only its own key,
    # never the first request's leftovers.
    assert second["dirtied"] == {"cycle"}
    assert first["session"] is not second["session"]
    assert first["mounted"] == [{"id": "a"}]
    # No X-PJX-Mounted header on the second request: MountedManifest.parse()
    # answers "nothing is mounted" as [], never None (verified against
    # pyjinhx2/client/inject.py's parse() — a missing/unreadable header always
    # falls through to `return []`).
    assert second["mounted"] == []
    assert current_session() is None
    assert get_dirtied() == set()


def test_cold_mount_returns_t1_response_via_testclient():
    app = make_app()
    STORE["card-1"] = 7

    @app.get("/card")
    def card() -> CycleCard:
        # render_level() only auto-mounts children discovered via ChildRef; a
        # component returned as the request's own root has no parent to do
        # that for it, so the handler mounts it itself before the render.
        component = CycleCard(id="a", pjx_key="card-1")
        component.pjx_mount()
        return component

    with TestClient(app) as client:
        response = client.get("/card")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "cycle card-1" in response.text
    # A cold mount is T1: the runtime is inlined because the client sent no
    # X-PJX-Mounted header.
    assert "<script>" in response.text
    assert "pjx" in response.text
    # The render mounted the component, so its load() ran exactly once.
    assert LOAD_CALLS == ["card-1"]
