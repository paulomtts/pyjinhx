import json

import pytest

from pyjinhx import BaseComponent, MountedManifest, PJX_MOUNTED_HEADER, Renderer

pytestmark = pytest.mark.pjx_runtime


class Page(BaseComponent):
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
    html = str(Page(id="page")._render(source="<html><body>hi</body></html>"))
    assert "htmx:configRequest" in html
    assert "X-PJX-Mounted" in html
    assert html.count("htmx:configRequest") == 1


def test_root_render_injects_runtime_when_manifest_header_missing():
    request = _Request({})
    html = str(
        Page(id="page")._render(
            source="<html><body>hi</body></html>",
            client=request,
        )
    )
    assert "htmx:configRequest" in html


def test_root_render_skips_runtime_when_manifest_header_present():
    request = _Request({PJX_MOUNTED_HEADER: "[]"})
    html = str(
        Page(id="page")._render(
            source="<html><body>hi</body></html>",
            client=request,
        )
    )
    assert "htmx:configRequest" not in html


def test_root_render_skips_runtime_for_valid_manifest():
    manifest = json.dumps(
        [{"id": "page", "type": "Page", "hash": "abc123", "key": None}]
    )
    request = _Request({PJX_MOUNTED_HEADER: manifest})
    html = str(
        Page(id="page")._render(
            source="<html><body>hi</body></html>",
            client=request,
        )
    )
    assert "htmx:configRequest" not in html


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
