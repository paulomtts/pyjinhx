"""L2.2.3: the per-session asset manifest — resolved, ordered CSS/JS URLs."""

import dataclasses
import threading
from pathlib import Path

import pytest

from pyjinhx.assets import AssetManifest, AssetMode, asset_manifest
from pyjinhx.session import RenderSession, request_scope

A_CSS = Path("/app/components/a.css")
B_CSS = Path("/app/components/b.css")
Y_JS = Path("/app/components/y.js")
Z_JS = Path("/app/components/z.js")


def by_name(path: Path) -> str:
    """A trivial resolver: URL is the filename under a fixed static prefix."""
    return f"/static/{path.name}"


def _session() -> RenderSession:
    """A bare session; assets are set-added directly, no render needed.

    Modes stay at their INLINE default and are never exercised — the manifest
    is mode-independent, and nothing here reads a file off disk, so the
    non-existent paths above are safe.
    """
    return RenderSession()


def test_manifest_empty_session_returns_empty_tuples():
    manifest = asset_manifest(_session(), resolver=by_name)
    assert manifest == AssetManifest(stylesheets=(), scripts=())


def test_manifest_resolves_and_sorts_css_paths_alphabetically():
    session = _session()
    session.css_assets.add(B_CSS)
    session.css_assets.add(A_CSS)
    manifest = asset_manifest(session, resolver=by_name)
    assert manifest.stylesheets == ("/static/a.css", "/static/b.css")


def test_manifest_resolves_and_sorts_js_paths_alphabetically():
    session = _session()
    session.js_assets.add(Z_JS)
    session.js_assets.add(Y_JS)
    manifest = asset_manifest(session, resolver=by_name)
    assert manifest.scripts == ("/static/y.js", "/static/z.js")


def test_manifest_keeps_stylesheets_and_scripts_separate():
    session = _session()
    session.css_assets.add(A_CSS)
    session.js_assets.add(Y_JS)
    manifest = asset_manifest(session, resolver=by_name)
    assert manifest.stylesheets == ("/static/a.css",)
    assert manifest.scripts == ("/static/y.js",)


def test_manifest_calls_resolver_exactly_once_per_path():
    session = _session()
    session.css_assets.update({A_CSS, B_CSS})
    session.js_assets.add(Y_JS)
    calls: list[Path] = []

    def recording(path: Path) -> str:
        calls.append(path)
        return by_name(path)

    asset_manifest(session, resolver=recording)
    assert sorted(calls, key=str) == [A_CSS, B_CSS, Y_JS]


def test_manifest_is_deterministic_across_repeated_calls():
    session = _session()
    session.css_assets.update({A_CSS, B_CSS})
    session.js_assets.update({Y_JS, Z_JS})
    assert asset_manifest(session, resolver=by_name) == asset_manifest(
        session, resolver=by_name
    )


def test_manifest_ignores_css_js_mode():
    session = _session()
    session.css_assets.add(A_CSS)
    session.js_assets.add(Y_JS)
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.NONE
    manifest = asset_manifest(session, resolver=by_name)
    assert manifest.stylesheets == ("/static/a.css",)
    assert manifest.scripts == ("/static/y.js",)


def test_manifest_reads_the_session_argument_not_active_scope():
    target = _session()
    target.css_assets.add(A_CSS)
    other = _session()
    other.css_assets.add(B_CSS)
    with request_scope(session=other):
        manifest = asset_manifest(target, resolver=by_name)
    assert manifest.stylesheets == ("/static/a.css",)


def test_concurrent_sessions_do_not_leak_into_each_others_manifest():
    seen: dict[str, AssetManifest] = {}
    started = threading.Barrier(2)

    def run(name: str, css: Path) -> None:
        session = _session()
        session.css_assets.add(css)
        with request_scope(session=session):
            started.wait()
            seen[name] = asset_manifest(session, resolver=by_name)

    threads = [
        threading.Thread(target=run, args=("a", A_CSS)),
        threading.Thread(target=run, args=("b", B_CSS)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert seen["a"].stylesheets == ("/static/a.css",)
    assert seen["b"].stylesheets == ("/static/b.css",)


def test_resolver_exception_propagates():
    session = _session()
    session.css_assets.add(A_CSS)

    def boom(path: Path) -> str:
        raise RuntimeError("no url for you")

    with pytest.raises(RuntimeError, match="no url for you"):
        asset_manifest(session, resolver=boom)


def test_asset_manifest_is_frozen():
    manifest = asset_manifest(_session(), resolver=by_name)
    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.stylesheets = ("/static/injected.css",)  # type: ignore[misc]
