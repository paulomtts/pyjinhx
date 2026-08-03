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


def _reset_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty the one-slot backend registry for the duration of a test.

    Also evicts ``pyjinhx.integrations.fastapi`` from ``sys.modules``: once any
    earlier test in this file has imported it (e.g.
    ``test_setup_wires_a_fastapi_app_through_the_backend``), a bare
    ``import pyjinhx.integrations.fastapi`` is a cache hit that does not
    re-execute the module body, so ``register_backend(_BACKEND)`` never runs
    again and ``_load_backend()``'s ``assert backend is not None`` trips even
    though the fall-through path is otherwise exercised correctly. Deleting
    the module from ``sys.modules`` forces the next import to re-run it.
    """
    import sys

    from pyjinhx.integrations import base

    monkeypatch.setattr(base, "_backend", None)
    monkeypatch.delitem(sys.modules, "pyjinhx.integrations.fastapi", raising=False)


class _SentinelBackend:
    """A backend object that is not the FastAPI one, to prove identity."""

    def is_installed(self, app: object) -> bool:
        return False

    def mark_installed(self, app: object) -> None: ...

    def mount_static(self, app: object, directory: str) -> None: ...

    def on_startup(self, app: object) -> None: ...

    def on_shutdown(self, app: object) -> None: ...

    def to_response(self, result: object, request: object | None) -> object:
        return result


def test_load_backend_returns_an_already_registered_backend(
    monkeypatch: pytest.MonkeyPatch,
):
    from pyjinhx.integrations.base import IntegrationBackend, register_backend

    _reset_registry(monkeypatch)

    def _no_probe(name: str):
        raise AssertionError(f"_find_spec must not be called, got {name!r}")

    monkeypatch.setattr(config, "_find_spec", _no_probe)

    sentinel = _SentinelBackend()
    assert isinstance(sentinel, IntegrationBackend)
    register_backend(sentinel)

    assert config._load_backend() is sentinel


def test_load_backend_does_not_import_the_adapter_when_one_is_registered(
    monkeypatch: pytest.MonkeyPatch,
):
    import builtins

    from pyjinhx.integrations.base import register_backend

    _reset_registry(monkeypatch)
    monkeypatch.setattr(config, "_find_spec", lambda name: object())

    real_import = builtins.__import__
    imported: list[str] = []

    def _tracking_import(name: str, *args: object, **kwargs: object):
        imported.append(name)
        return real_import(name, *args, **kwargs)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(builtins, "__import__", _tracking_import)

    sentinel = _SentinelBackend()
    register_backend(sentinel)

    assert config._load_backend() is sentinel
    assert not any(name.startswith("pyjinhx.integrations.fastapi") for name in imported)


def test_load_backend_imports_the_adapter_when_nothing_is_registered(
    monkeypatch: pytest.MonkeyPatch,
):
    _reset_registry(monkeypatch)
    monkeypatch.setattr(config, "_find_spec", lambda name: object())

    from pyjinhx.integrations.fastapi import _BACKEND

    assert config._load_backend() is _BACKEND


def test_load_backend_names_the_extra_when_nothing_is_registered(
    monkeypatch: pytest.MonkeyPatch,
):
    _reset_registry(monkeypatch)
    monkeypatch.setattr(config, "_find_spec", lambda name: None)

    with pytest.raises(ImportError, match=r"pyjinhx\[fastapi\]"):
        config._load_backend()
