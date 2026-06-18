import json

import pytest

from pyjinhx import BaseComponent, Registry, Renderer
from pyjinhx.assets import _runtime_injected
from pyjinhx.client import PJX_MOUNTED_HEADER, MountedManifest

pytestmark = pytest.mark.pjx_runtime


class RuntimePage(BaseComponent):
    pass


class NestedChild(BaseComponent):
    label: str = "child"


class _Headers:
    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._mapping.get(name, default)


class _Request:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = _Headers(headers)


def test_mounted_manifest_is_present():
    assert MountedManifest.is_present(None) is False
    assert MountedManifest.is_present("") is False
    assert MountedManifest.is_present("[]") is True
    assert MountedManifest.is_present("not-json") is False
    assert MountedManifest.is_present([]) is True
    assert MountedManifest.is_present(
        [{"id": "counter", "type": "Counter", "hash": "abc"}]
    ) is True
    assert MountedManifest.is_present(_Request({})) is False
    assert MountedManifest.is_present(
        _Request({PJX_MOUNTED_HEADER: "[]"})
    ) is True


def test_root_render_injects_runtime_without_client():
    html = str(RuntimePage(id="page")._render(source="<html><body>hi</body></html>"))
    assert "htmx:configRequest" in html
    # "X-PJX-Mounted" is unique to pjx.js (htmx never references it), so it is a
    # reliable proxy for "pjx.js present exactly once" now that htmx — which also
    # contains "htmx:configRequest" — is inlined alongside it.
    assert html.count("X-PJX-Mounted") == 1
    # the vendored htmx transport is injected too
    assert "var htmx" in html


def test_root_render_injects_runtime_when_manifest_header_missing():
    request = _Request({})
    html = str(
        RuntimePage(id="page")._render(
            source="<html><body>hi</body></html>",
            client=request,
        )
    )
    assert "htmx:configRequest" in html


def test_root_render_skips_runtime_when_manifest_header_present():
    request = _Request({PJX_MOUNTED_HEADER: "[]"})
    html = str(
        RuntimePage(id="page")._render(
            source="<html><body>hi</body></html>",
            client=request,
        )
    )
    assert "htmx:configRequest" not in html


def test_root_render_skips_runtime_for_valid_manifest():
    manifest = json.dumps(
        [{"id": "page", "type": "RuntimePage", "hash": "abc123"}]
    )
    request = _Request({PJX_MOUNTED_HEADER: manifest})
    html = str(
        RuntimePage(id="page")._render(
            source="<html><body>hi</body></html>",
            client=request,
        )
    )
    assert "htmx:configRequest" not in html


def test_request_scope_injects_runtime_once_across_root_renders():
    with Registry.request_scope():
        first = str(RuntimePage(id="page-a")._render(source="<div>a</div>"))
        second = str(RuntimePage(id="page-b")._render(source="<div>b</div>"))
    assert first.count("X-PJX-Mounted") == 1
    assert "X-PJX-Mounted" not in second


def test_separate_request_scopes_each_inject_runtime():
    with Registry.request_scope():
        first = str(RuntimePage(id="page-a")._render(source="<div>a</div>"))
    with Registry.request_scope():
        second = str(RuntimePage(id="page-b")._render(source="<div>b</div>"))
    assert first.count("X-PJX-Mounted") == 1
    assert second.count("X-PJX-Mounted") == 1


def test_without_request_scope_each_root_render_injects_runtime():
    # conftest wraps every test in Registry.request_scope(); clear the
    # request-scoped flag to exercise the no-scope fallback.
    token = _runtime_injected.set(None)
    try:
        first = str(RuntimePage(id="page-a")._render(source="<div>a</div>"))
        second = str(RuntimePage(id="page-b")._render(source="<div>b</div>"))
    finally:
        _runtime_injected.reset(token)
    assert first.count("X-PJX-Mounted") == 1
    assert second.count("X-PJX-Mounted") == 1


def test_nested_render_does_not_inject_runtime():
    renderer = Renderer.get_default_renderer()
    session = renderer.new_session()
    html = str(
        NestedChild(id="child")._render(
            source="<span>{{ label }}</span>",
            base_context={},
            _renderer=renderer,
            _session=session,
        )
    )
    assert "htmx:configRequest" not in html
