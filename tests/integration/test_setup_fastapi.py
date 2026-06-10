from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pyjinhx import setup
from pyjinhx.cache import CacheScope, InvalidationBackend, LoadCache
from pyjinhx.client import ClientBackend


class _StubBackend(InvalidationBackend):
    def publish(self, keys: frozenset[str]) -> None:
        pass

    def start(self, handler) -> None:
        pass

    def stop(self) -> None:
        pass


def test_setup_without_app_no_backend_is_request():
    setup()
    assert LoadCache.scope() == CacheScope.REQUEST


def test_setup_without_app_with_backend_is_process():
    setup(invalidation_backend=_StubBackend())
    assert LoadCache.scope() == CacheScope.PROCESS


def test_setup_chains_existing_lifespan():
    events: list[str] = []

    @asynccontextmanager
    async def user_lifespan(_app):
        events.append("user_start")
        yield
        events.append("user_stop")

    app = FastAPI(lifespan=user_lifespan)
    setup(app)

    with TestClient(app) as _client:
        assert events == ["user_start"]
        assert LoadCache.scope() == CacheScope.REQUEST
    assert events == ["user_start", "user_stop"]


def test_setup_middleware_wires_client_backend():
    app = FastAPI()
    setup(app)

    @app.get("/")
    def index():
        backend = ClientBackend.current()
        assert backend is not None
        return "ok"

    with TestClient(app) as client:
        assert client.get("/").status_code == 200


def test_setup_is_idempotent():
    app = FastAPI()
    setup(app)
    # A second setup() (which would derive PROCESS from a backend) is a no-op.
    setup(app, invalidation_backend=_StubBackend())
    assert app.state.pyjinhx_setup is True

    with TestClient(app) as client:
        client.get("/")
    assert LoadCache.scope() == CacheScope.REQUEST


def test_setup_rejects_non_asgi_app():
    with pytest.raises(TypeError, match="Starlette/FastAPI-like app"):
        setup(object())
