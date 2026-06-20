from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import FileSystemLoader
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from pyjinhx import setup
from pyjinhx.cache import CacheScope, InvalidationBackend, LoadCache
from pyjinhx.client import ClientBackend
from pyjinhx.renderer import Renderer


@pytest.fixture
def restore_default_environment():
    # save/restore the process-wide default environment so components_root tests
    # don't leak state into the rest of the suite
    original = Renderer.peek_default_environment()
    yield
    Renderer.set_default_environment(original)


def _static_mounts(app):
    return [
        route
        for route in app.routes
        if isinstance(route, Mount) and route.path == "/static" and route.name == "static"
    ]


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


def test_setup_context_factory_threads_context():
    from pyjinhx.context import PjxContext

    app = FastAPI()
    setup(app, context_factory=lambda _request: "CTX")

    @app.get("/ctx")
    def ctx_route():
        return PjxContext.current()

    with TestClient(app) as client:
        assert client.get("/ctx").text == '"CTX"'


def test_setup_components_root_sets_default_environment(
    tmp_path, restore_default_environment
):
    app = FastAPI()
    setup(app, components_root=tmp_path)

    env = Renderer.peek_default_environment()
    assert env is not None
    assert isinstance(env.loader, FileSystemLoader)
    assert env.loader.searchpath[0] == str(tmp_path)


def test_setup_components_root_without_app(tmp_path, restore_default_environment):
    setup(components_root=tmp_path)

    env = Renderer.peek_default_environment()
    assert env is not None
    assert isinstance(env.loader, FileSystemLoader)
    assert env.loader.searchpath[0] == str(tmp_path)


def test_setup_static_root_mounts_static_files(tmp_path):
    app = FastAPI()
    setup(app, static_root=tmp_path)

    mounts = _static_mounts(app)
    assert len(mounts) == 1
    assert isinstance(mounts[0].app, StaticFiles)


def test_setup_static_root_without_app_raises():
    with pytest.raises(TypeError, match="static_root"):
        setup(static_root="/tmp")


def test_setup_no_roots_leaves_environment_and_no_mount(restore_default_environment):
    before = Renderer.peek_default_environment()
    app = FastAPI()
    setup(app)

    assert Renderer.peek_default_environment() is before
    assert _static_mounts(app) == []


def test_setup_static_root_idempotent_no_double_mount(tmp_path):
    app = FastAPI()
    setup(app, static_root=tmp_path)
    setup(app, static_root=tmp_path)

    assert len(_static_mounts(app)) == 1
