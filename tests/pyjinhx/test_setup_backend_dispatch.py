"""setup(app=...) dispatches through the registered backend, or says why it can't."""

from __future__ import annotations

import pytest

from pyjinhx import config
from pyjinhx.config import PjxSettings, setup


def test_setup_without_an_app_needs_no_backend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config, "_find_spec", lambda name: None)
    resolved = setup(settings=PjxSettings(inject_htmx=False))
    assert resolved.inject_htmx is False


def test_setup_with_an_app_and_no_extra_names_the_extra(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(config, "_find_spec", lambda name: None)
    with pytest.raises(ImportError, match=r"pyjinhx\[fastapi\]"):
        setup(app=object())


def test_setup_rejects_an_app_the_backend_does_not_accept():
    with pytest.raises(TypeError, match="add_middleware"):
        setup(app=object())


def test_setup_wires_a_fastapi_app_through_the_backend():
    from fastapi import FastAPI

    from pyjinhx.integrations.base import SETUP_FLAG

    app = FastAPI()
    setup(app=app)
    assert getattr(app.state, SETUP_FLAG) is True
    assert any(
        middleware.cls.__name__ == "PjxScopeMiddleware"  # pyright: ignore[reportAttributeAccessIssue]
        for middleware in app.user_middleware
    )
