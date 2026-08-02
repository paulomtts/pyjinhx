"""One live FastAPI request cycle: config, middleware, context and dev together.

Unlike the per-module tests, nothing here enters ``request_scope()`` by hand or
builds a fake request: every assertion is made on an HTTP response TestClient
returned, or on state read from inside a handler the middleware called.
"""

import dataclasses
import importlib
import json
import logging
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from pyjinhx2 import discovery, registry
from pyjinhx2.assets import asset_token
from pyjinhx2.config import PjxSettings
from pyjinhx2.context import PjxContext
from pyjinhx2.dev import warn_unconsumed_mutations
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


class CycleBadge(ReactiveComponent, react=(Keys.CYCLE,)):
    """A second reactive region, this one carrying CSS and JS assets."""

    pjx_key: Annotated[str, PjxKey()] = ""

    def load(self) -> int:
        LOAD_CALLS.append(f"badge:{self.pjx_key}")
        return STORE.get(self.pjx_key, 0)


ASSET_DIR = Path(__file__).parent.parent.parent / "templates"


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
    discovery.build_registry(template_dir, [CycleCard, CycleBadge])
    # `_resolve_template_path` probes the class's *defining module* directory
    # (this test file's), not the dir handed to build_registry, so the
    # descriptor is repointed at the bare template name the middleware's
    # FileSystemLoader will join under tests/templates.
    CycleCard.__pjx_descriptor__ = dataclasses.replace(
        CycleCard.__pjx_descriptor__, template_path=Path("cycle_card.pjx")
    )
    CycleBadge.__pjx_descriptor__ = dataclasses.replace(
        CycleBadge.__pjx_descriptor__,
        template_path=Path("cycle_badge.pjx"),
        css_paths=(ASSET_DIR / "cycle_badge.css",),
        js_paths=(ASSET_DIR / "cycle_badge.js",),
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


def badge_entry(instance_id: str, load: object, hash_: str = "stale") -> dict:
    """One synthetic X-PJX-Mounted entry naming a mounted CycleBadge region."""
    return {"type": "cycle_badge", "id": instance_id, "load": load, "hash": hash_}


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


def test_mutation_round_trip_returns_gated_oob_swap():
    app = make_app()
    STORE["card-1"] = 0

    @app.post("/bump")
    def bump(request: Request):
        # Stands in for the Load path in this request: the region the client
        # reports as mounted has to be resolvable before fan-out can swap it.
        registry.register_instance(
            CycleCard.__name__, "a", CycleCard(id="a", pjx_key="card-1")
        )
        Counter().bump("card-1")
        invalidate(get_dirtied())
        return ReactiveResponse(primary="", mounted=request)

    with TestClient(app) as client:
        response = client.post(
            "/bump",
            headers={"X-PJX-Mounted": json.dumps([entry("a", load="card-1")])},
        )

    assert response.status_code == 200
    # An OOB-only body: htmx is told not to swap the trigger.
    assert response.headers["HX-Reswap"] == "none"
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in response.text
    assert "cycle card-1" in response.text
    # The mutation moved the store and the swap re-ran load() against it.
    assert STORE["card-1"] == 1
    assert LOAD_CALLS == ["card-1"]


def test_unchanged_region_is_gated_out_of_the_oob_swap():
    app = make_app()
    STORE["card-1"] = 0
    fresh_hash = CycleCard(id="a", pjx_key="card-1").state_hash()

    @app.post("/bump")
    def bump(request: Request):
        registry.register_instance(
            CycleCard.__name__, "a", CycleCard(id="a", pjx_key="card-1")
        )
        dirty(Keys.CYCLE)
        invalidate(get_dirtied())
        return ReactiveResponse(primary="", mounted=request)

    with TestClient(app) as client:
        response = client.post(
            "/bump",
            headers={
                "X-PJX-Mounted": json.dumps(
                    [entry("a", load="card-1", hash_=fresh_hash)]
                )
            },
        )

    # Dirty says the data may have moved; the hash says this region's output
    # did not, so the swap that would replace it with itself is dropped.
    assert "hx-swap-oob" not in response.text


def test_mutation_round_trip_demo_swaps_dirty_regions_and_ships_missing_assets():
    """One request through every leg: dirty -> evict -> fan-out -> gate -> assets."""
    app = make_app()
    STORE["card-1"] = 0
    STORE["card-2"] = 41
    unchanged_hash = CycleCard(id="b", pjx_key="card-2").state_hash()

    @app.post("/bump")
    def bump(request: Request):
        for instance_id, cls, key in (
            ("a", CycleCard, "card-1"),
            ("b", CycleCard, "card-2"),
            ("c", CycleBadge, "card-1"),
        ):
            registry.register_instance(
                cls.__name__, instance_id, cls(id=instance_id, pjx_key=key)
            )
        Counter().bump("card-1")
        return ReactiveResponse(primary="", mounted=request, assets=request)

    with TestClient(app) as client:
        response = client.post(
            "/bump",
            headers={
                "X-PJX-Mounted": json.dumps(
                    [
                        entry("a", load="card-1"),
                        entry("b", load="card-2", hash_=unchanged_hash),
                        badge_entry("c", load="card-1"),
                        # A region the registry no longer knows about: gone.
                        badge_entry("gone", load="card-9"),
                    ]
                ),
                "X-PJX-Assets": "[]",
            },
        )

    body = response.text
    # 1-3: the mutation moved the store, eviction let the swap re-read it.
    assert STORE["card-1"] == 1
    # 4a: the dirty+changed region swaps.
    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in body
    # 4b: dirty but byte-identical output — gated out.
    assert "[data-pjx-id='b']" not in body
    # 4c: a region the registry lost is deleted rather than re-rendered.
    assert "hx-swap-oob=\"delete:[data-pjx-id='gone']\"" in body
    # 5: the asset-bearing region's CSS and JS ride along, head-targeted.
    css_token = asset_token(ASSET_DIR / "cycle_badge.css")
    js_token = asset_token(ASSET_DIR / "cycle_badge.js")
    assert f'<style data-pjx-asset="{css_token}" hx-swap-oob="beforeend:head">' in body
    assert f'<script data-pjx-asset="{js_token}" hx-swap-oob="beforeend:head">' in body
    # 6: nothing for htmx's default swap to place.
    assert response.headers["HX-Reswap"] == "none"


def test_round_trip_does_not_resend_assets_the_client_already_reports():
    app = make_app()
    STORE["card-1"] = 0
    css_token = asset_token(ASSET_DIR / "cycle_badge.css")
    js_token = asset_token(ASSET_DIR / "cycle_badge.js")

    @app.post("/bump")
    def bump(request: Request):
        registry.register_instance(
            CycleBadge.__name__, "c", CycleBadge(id="c", pjx_key="card-1")
        )
        Counter().bump("card-1")
        return ReactiveResponse(primary="", mounted=request, assets=request)

    with TestClient(app) as client:
        response = client.post(
            "/bump",
            headers={
                "X-PJX-Mounted": json.dumps([badge_entry("c", load="card-1")]),
                "X-PJX-Assets": json.dumps([css_token, js_token]),
            },
        )

    assert "hx-swap-oob=\"outerHTML:[data-pjx-id='c']\"" in response.text
    assert "data-pjx-asset" not in response.text


def test_a_malformed_assets_header_means_the_client_has_nothing():
    app = make_app()
    STORE["card-1"] = 0

    @app.post("/bump")
    def bump(request: Request):
        registry.register_instance(
            CycleBadge.__name__, "c", CycleBadge(id="c", pjx_key="card-1")
        )
        Counter().bump("card-1")
        return ReactiveResponse(primary="", mounted=request, assets=request)

    with TestClient(app) as client:
        response = client.post(
            "/bump",
            headers={
                "X-PJX-Mounted": json.dumps([badge_entry("c", load="card-1")]),
                "X-PJX-Assets": "{not json",
            },
        )

    # An unreadable browser-supplied header re-delivers rather than raising.
    assert (
        f'data-pjx-asset="{asset_token(ASSET_DIR / "cycle_badge.css")}"'
        in response.text
    )


def test_pjx_context_current_populated_inside_live_handler():
    app = FastAPI()
    apply_setup(
        app,
        PjxSettings(),
        context_factory=lambda request: {"user": "ada"},
    )
    seen: dict[str, object] = {}

    @app.post("/ctx")
    def ctx():
        dirty(Keys.CYCLE)
        context = PjxContext.current()
        seen["session"] = context.session
        seen["mounted"] = context.mounted
        seen["assets"] = context.assets
        seen["trigger"] = context.trigger
        seen["dirtied"] = set(context.dirtied)
        seen["app_context"] = context.app_context
        seen["request_url"] = str(context.request.url) if context.request else None
        return {"ok": True}

    with TestClient(app) as client:
        client.post(
            "/ctx",
            headers={
                "X-PJX-Mounted": json.dumps([entry("a", load="card-1")]),
                "X-PJX-Assets": '["tok"]',
                "X-PJX-Trigger": '{"id": "a"}',
            },
        )

    assert seen["session"] is not None
    assert seen["mounted"] == [entry("a", load="card-1")]
    assert seen["assets"] == frozenset({"tok"})
    assert seen["trigger"] == {"id": "a"}
    assert seen["dirtied"] == {"cycle"}
    assert seen["app_context"] == {"user": "ada"}
    request_url = seen["request_url"]
    assert isinstance(request_url, str) and request_url.endswith("/ctx")


def test_pjx_context_current_raises_outside_request_scope():
    app = make_app()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/ping").json() == {"ok": True}

    # Setup is app-wide but the scope is per-request: outside one, no amount of
    # prior wiring makes a context available.
    with pytest.raises(NoActiveRequestScope):
        PjxContext.current()


def _unconsumed_app(**settings_kwargs) -> FastAPI:
    """An app whose endpoint dirties a key nothing in the request loaded under."""
    app = make_app(**settings_kwargs)

    @app.post("/orphan")
    def orphan():
        dirty(Keys.ORPHAN)
        warn_unconsumed_mutations()
        return {"ok": True}

    return app


def test_reactive_dev_warns_on_unconsumed_mutation_live_request(caplog):
    app = _unconsumed_app(reactive_dev=True)

    with caplog.at_level(logging.WARNING, logger="pyjinhx"), TestClient(app) as client:
        assert client.post("/orphan").json() == {"ok": True}

    warnings = [record.getMessage() for record in caplog.records]
    assert any("nobody-reads-this" in message for message in warnings)


def test_reactive_dev_silent_when_disabled_live_request(caplog):
    app = _unconsumed_app()

    with caplog.at_level(logging.WARNING, logger="pyjinhx"), TestClient(app) as client:
        assert client.post("/orphan").json() == {"ok": True}

    warnings = [record.getMessage() for record in caplog.records]
    assert not any("nobody-reads-this" in message for message in warnings)


def test_lower_layers_do_not_import_the_wiring_layer():
    """The reactive package and the session spine never reach back up."""
    import ast
    import pkgutil

    def imported_module_names(source: str) -> set[str]:
        """Every dotted module name a real ``import``/``from`` statement names.

        AST-based rather than a substring scan: ``from pyjinhx2 import
        discovery, registry`` never spells the substring "pyjinhx2.registry",
        so a text search over the source would silently miss exactly the
        import shape this codebase's lower layers use.
        """
        names: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
                names.update(f"{node.module}.{alias.name}" for alias in node.names)
        return names

    upper = {
        "pyjinhx2.config",
        "pyjinhx2.context",
        "pyjinhx2.dev",
        "pyjinhx2.integrations",
    }
    lower = ["pyjinhx2.session"] + [
        f"pyjinhx2.reactive.{module.name}"
        for module in pkgutil.iter_modules(
            importlib.import_module("pyjinhx2.reactive").__path__
        )
    ]

    offenders: list[tuple[str, str]] = []
    for name in lower:
        source = Path(importlib.import_module(name).__file__ or "").read_text()
        imported = imported_module_names(source)
        for upper_name in upper:
            if upper_name in imported or any(
                mod.startswith(f"{upper_name}.") for mod in imported
            ):
                offenders.append((name, upper_name))

    assert offenders == []
