"""The backend interface works with a fake backend and no web framework."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest

from pyjinhx._component import BaseComponent
from pyjinhx.integrations.base import (
    SETUP_FLAG,
    ContextFactory,
    IntegrationBackend,
    load_context_for,
)
from pyjinhx.reactive.response import ReactiveResponse
from pyjinhx.session import current_session, get_load_context, request_scope


def test_module_has_no_web_framework_imports() -> None:
    source = sys.modules["pyjinhx.integrations.base"].__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "fastapi" not in text
    assert "starlette" not in text


def test_setup_flag_name_is_stable() -> None:
    assert SETUP_FLAG == "pyjinhx_setup"
    assert IntegrationBackend is not None


@dataclass
class FakeApp:
    """Stands in for a framework application object."""

    installed: bool = False
    static_mounts: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)


@dataclass
class FakeResponse:
    """Stands in for a framework HTML response."""

    body: str
    headers: dict[str, str] = field(default_factory=dict)


class FakeBackend:
    """A backend with no web framework behind it, used to drive the interface."""

    def __init__(self, context_factory: ContextFactory | None = None) -> None:
        self.context_factory = context_factory

    def is_installed(self, app: object) -> bool:
        assert isinstance(app, FakeApp)
        return app.installed

    def mark_installed(self, app: object) -> None:
        assert isinstance(app, FakeApp)
        app.installed = True

    def mount_static(self, app: object, directory: str) -> None:
        assert isinstance(app, FakeApp)
        app.static_mounts.append(directory)

    def on_startup(self, app: object) -> None:
        assert isinstance(app, FakeApp)
        app.events.append("startup")

    def on_shutdown(self, app: object) -> None:
        assert isinstance(app, FakeApp)
        app.events.append("shutdown")

    def to_response(self, result: object, request: object | None) -> object:
        if isinstance(result, ReactiveResponse):
            return FakeResponse(str(result.body), dict(result.headers))
        if isinstance(result, BaseComponent):
            return FakeResponse(type(result).__name__)
        return result

    def handle(self, request: object, handler: Callable[[], object]) -> object:
        """Bind one request scope around ``handler`` and adapt its return."""
        load_context = load_context_for(request, self.context_factory)
        with request_scope(load_context=load_context):
            return self.to_response(handler(), request)


def test_fake_backend_satisfies_the_protocol() -> None:
    assert isinstance(FakeBackend(), IntegrationBackend)


def test_load_context_is_visible_inside_the_scope_and_cleared_outside() -> None:
    backend = FakeBackend(context_factory=lambda request: {"user": request})
    seen: dict[str, object] = {}

    def handler() -> object:
        seen["session"] = current_session()
        seen["context"] = get_load_context()
        return "plain"

    assert backend.handle("alice", handler) == "plain"
    assert seen["session"] is not None
    assert seen["context"] == {"user": "alice"}
    assert current_session() is None
    assert get_load_context() is None


def test_no_context_factory_leaves_the_load_context_unset() -> None:
    backend = FakeBackend()
    seen: list[object] = []
    backend.handle("bob", lambda: seen.append(get_load_context()))
    assert seen == [None]


def test_scope_is_reset_when_the_handler_raises() -> None:
    backend = FakeBackend(context_factory=lambda request: request)

    def boom() -> object:
        raise ValueError("handler exploded")

    with pytest.raises(ValueError, match="handler exploded"):
        backend.handle("carol", boom)
    assert current_session() is None
    assert get_load_context() is None


def test_setup_guard_reports_installed_only_after_marking() -> None:
    backend = FakeBackend()
    app = FakeApp()
    assert backend.is_installed(app) is False
    backend.mark_installed(app)
    assert backend.is_installed(app) is True
    backend.mark_installed(app)
    assert backend.is_installed(app) is True


def test_mount_static_records_the_directory() -> None:
    backend = FakeBackend()
    app = FakeApp()
    backend.mount_static(app, "assets")
    assert app.static_mounts == ["assets"]


def test_lifecycle_hooks_fire_in_order() -> None:
    backend = FakeBackend()
    app = FakeApp()
    backend.on_startup(app)
    backend.on_shutdown(app)
    assert app.events == ["startup", "shutdown"]


def test_to_response_adapts_reactive_and_passes_others_through() -> None:
    backend = FakeBackend()
    reactive = ReactiveResponse(primary="<div>hi</div>")
    adapted = backend.to_response(reactive, None)
    assert isinstance(adapted, FakeResponse)
    assert adapted.body == "<div>hi</div>"
    assert adapted.headers == {}
    assert backend.to_response({"json": True}, None) == {"json": True}


def test_test_file_does_not_import_a_web_framework() -> None:
    with open(__file__, encoding="utf-8") as handle:
        text = handle.read()
    banned = "fast" + "api", "star" + "lette"
    occurrences = [name for name in banned if text.count(name) > 1]
    assert occurrences == []
