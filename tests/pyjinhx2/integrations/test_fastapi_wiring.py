"""The FastAPI adapter: request scope, header parsing, T1/T2 response adaptation."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pyjinhx2.component import BaseComponent
from pyjinhx2.integrations.fastapi import apply_setup
from pyjinhx2.config import PjxSettings


def test_apply_setup_is_importable():
    assert callable(apply_setup)


def _settings(**kwargs) -> PjxSettings:
    return PjxSettings(**kwargs)


def test_apply_setup_registers_the_scope_middleware():
    app = FastAPI()
    apply_setup(app, _settings())
    assert any(
        middleware.cls.__name__ == "PjxScopeMiddleware"
        for middleware in app.user_middleware
    )


def test_apply_setup_is_idempotent():
    app = FastAPI()
    apply_setup(app, _settings())
    apply_setup(app, _settings())
    names = [m.cls.__name__ for m in app.user_middleware]
    assert names.count("PjxScopeMiddleware") == 1


def test_static_files_are_mounted_when_static_root_is_set(tmp_path: Path):
    app = FastAPI()
    apply_setup(app, _settings(static_root=tmp_path))
    assert any(getattr(route, "name", None) == "static" for route in app.routes)


def test_no_static_mount_without_static_root():
    app = FastAPI()
    apply_setup(app, _settings())
    assert not any(getattr(route, "name", None) == "static" for route in app.routes)


def test_lifespan_configures_and_shuts_down_around_no_prior_lifespan():
    from pyjinhx2.config import current_settings

    app = FastAPI()
    settings = _settings(inject_htmx=False)
    apply_setup(app, settings)
    with TestClient(app):
        assert current_settings().inject_htmx is False
    assert current_settings().inject_htmx is True


def test_lifespan_wraps_an_app_provided_lifespan():
    from contextlib import asynccontextmanager as _acm

    from pyjinhx2.config import current_settings

    seen: list[bool] = []

    @_acm
    async def app_lifespan(_app):
        seen.append(current_settings().inject_htmx)
        yield

    app = FastAPI(lifespan=app_lifespan)
    apply_setup(app, _settings(inject_htmx=False))
    with TestClient(app):
        pass
    assert seen == [False]
