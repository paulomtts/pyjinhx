from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pyjinhx import (
    CacheScope,
    ClientBackend,
    get_load_cache_scope,
    setup,
    shutdown_pyjinhx,
)
from pyjinhx.reactive.invalidation import reset_invalidation_state


@pytest.fixture(autouse=True)
def _clean_config_state():
    shutdown_pyjinhx()
    reset_invalidation_state()
    yield
    shutdown_pyjinhx()
    reset_invalidation_state()


def test_setup_without_app_configures_process():
    setup(cache_scope=CacheScope.REQUEST)
    assert get_load_cache_scope() == CacheScope.REQUEST


def test_setup_chains_existing_lifespan():
    events: list[str] = []

    @asynccontextmanager
    async def user_lifespan(_app):
        events.append("user_start")
        yield
        events.append("user_stop")

    app = FastAPI(lifespan=user_lifespan)
    setup(app, cache_scope=CacheScope.REQUEST)

    with TestClient(app) as _client:
        assert events == ["user_start"]
        assert get_load_cache_scope() == CacheScope.REQUEST
    assert events == ["user_start", "user_stop"]


def test_setup_middleware_wires_client_backend():
    app = FastAPI()
    setup(app, cache_scope=CacheScope.REQUEST)

    @app.get("/")
    def index():
        backend = ClientBackend.current()
        assert backend is not None
        return "ok"

    with TestClient(app) as client:
        assert client.get("/").status_code == 200


def test_setup_is_idempotent():
    app = FastAPI()
    setup(app, cache_scope=CacheScope.REQUEST)
    setup(app, cache_scope=CacheScope.PROCESS)
    assert app.state.pyjinhx_setup is True

    with TestClient(app) as client:
        client.get("/")
    assert get_load_cache_scope() == CacheScope.REQUEST


def test_setup_rejects_non_asgi_app():
    with pytest.raises(TypeError, match="Starlette/FastAPI-like app"):
        setup(object(), cache_scope=CacheScope.REQUEST)
