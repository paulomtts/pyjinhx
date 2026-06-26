from collections.abc import Generator
from typing import Any

import pytest

from pyjinhx import Registry
from pyjinhx.assets import RenderSession
from pyjinhx.cache import CacheScope, InvalidationHub, LoadCache
from pyjinhx.client import ClientBackend
from pyjinhx.config import shutdown_pyjinhx
from pyjinhx.mutations import MutationTracker
from pyjinhx.renderer import Renderer


def _noop_inject_runtime(
    session: RenderSession,
    *,
    policy: Any,
    client: object | None = None,
) -> None:
    return


@pytest.fixture(autouse=True)
def _suppress_pjx_runtime_injection(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("pjx_runtime"):
        return
    monkeypatch.setattr(
        "pyjinhx.assets.inject_runtime",
        _noop_inject_runtime,
    )


@pytest.fixture(autouse=True)
def _clean_config_state() -> Generator[None, None, None]:
    shutdown_pyjinhx()
    InvalidationHub.reset()
    Renderer.set_default_environment(None)
    yield
    shutdown_pyjinhx()
    InvalidationHub.reset()
    Renderer.set_default_environment(None)


@pytest.fixture(autouse=True)
def _isolate_reactive_state(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """
    Reset pyjinhx reactive state around every test inside a request scope.

    Mirrors production: load() cache (REQUEST scope), instance registry, and
    mutation tracking are all request-scoped. Tests marked ``no_request_scope``
    get the same state reset but run OUTSIDE a request scope (e.g. to assert
    behavior when ``current_directives()`` is ``None``).
    """
    original_scope = LoadCache.scope()
    LoadCache.clear()
    MutationTracker.clear()
    InvalidationHub.reset()
    ClientBackend.reset()
    Registry.clear_instances()
    LoadCache.set_scope(CacheScope.REQUEST)
    if request.node.get_closest_marker("no_request_scope"):
        yield
    else:
        with Registry.request_scope():
            yield
    LoadCache.clear()
    MutationTracker.clear()
    InvalidationHub.reset()
    ClientBackend.reset()
    Registry.clear_instances()
    LoadCache.set_scope(original_scope)
