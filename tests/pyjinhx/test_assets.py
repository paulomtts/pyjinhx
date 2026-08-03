"""L2.2.1: per-request accumulation of descriptor CSS/JS paths, deduped by path."""

import threading
from dataclasses import replace
from pathlib import Path

from pyjinhx.assets import AssetMode, all_assets
from pyjinhx.component import BaseComponent
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.rendering import render
from pyjinhx.session import (
    RenderSession,
    accumulate_assets,
    request_scope,
)

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

CSS = Path("/app/components/box.css")
JS = Path("/app/components/box.js")


def _plain_descriptor(owner: type) -> ClassDescriptor:
    """A hand-built descriptor pointed at the shared plain_div.html fixture.

    Bypasses the real MRO/filesystem template walk on purpose (there is no
    `__pjx_template__` override attribute in production code) — same pattern
    test_render_level.py uses.
    """
    return ClassDescriptor(
        template_path=_TEMPLATE_DIR / "plain_div.html",
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": owner},
    )


class PlainBox(BaseComponent):
    """Component rendered against a hand-built descriptor, not MRO discovery."""


class PlainSibling(BaseComponent):
    """Second class used to prove cross-class dedup on a shared asset path."""


PlainBox.__pjx_descriptor__ = _plain_descriptor(PlainBox)
PlainSibling.__pjx_descriptor__ = _plain_descriptor(PlainSibling)


def with_assets(cls, *, css=(), js=()):
    """Point a class's frozen descriptor at the given asset paths (read-only use)."""
    cls.__pjx_descriptor__ = replace(
        cls.__pjx_descriptor__, css_paths=tuple(css), js_paths=tuple(js)
    )
    return cls


def _accumulating_session() -> RenderSession:
    """A fresh RenderSession with the asset accumulator wired to on_rendered.

    Deliberately not entered into a request_scope(): accumulate_assets reads
    the session render_level() passes to it, not the request_scope ContextVar,
    so a plain render(component, session) call — the convention used
    throughout the rest of the suite — must accumulate on its own.

    Modes set to NONE: this file exercises accumulation into css_assets/
    js_assets (#429), not #430's emission. The CSS/JS constants above point at
    paths that don't exist on disk on purpose (accumulation never reads the
    file); #430 wired render() to inline-read accumulated paths by default,
    so leaving these sessions on INLINE would make render() raise on a path
    that was never meant to be readable.
    """
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.NONE
    return session


def test_accumulates_css_path_from_single_component():
    with_assets(PlainBox, css=[CSS])
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        assert session.css_assets == {CSS}


def test_accumulates_js_path_from_single_component():
    with_assets(PlainBox, js=[JS])
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        assert session.js_assets == {JS}


def test_dedups_same_path_across_two_instances_of_same_class():
    with_assets(PlainBox, css=[CSS])
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        render(PlainBox(), session)
        assert session.css_assets == {CSS}


def test_dedups_same_path_across_two_different_classes_sharing_a_co_located_asset():
    with_assets(PlainBox, css=[CSS])
    with_assets(PlainSibling, css=[CSS])
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        render(PlainSibling(), session)
        assert session.css_assets == {CSS}


def test_no_op_for_component_with_no_css_or_js_paths():
    with_assets(PlainBox)
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        assert session.css_assets == set()
        assert session.js_assets == set()


def test_accumulator_resets_between_request_scopes():
    with_assets(PlainBox, css=[CSS])
    with request_scope(session=_accumulating_session()) as first:
        render(PlainBox(), first)
        assert first.css_assets == {CSS}
    with request_scope(session=_accumulating_session()) as second:
        assert second is not first
        assert second.css_assets == set()


def test_two_concurrent_request_scopes_do_not_leak_into_each_other():
    with_assets(PlainBox, css=[CSS])
    with_assets(PlainSibling, css=[Path("/app/components/sibling.css")])
    seen: dict[str, set[Path]] = {}
    started = threading.Barrier(2)

    def run(name, component_cls):
        with request_scope(session=_accumulating_session()) as session:
            started.wait()
            render(component_cls(), session)
            seen[name] = set(session.css_assets)

    threads = [
        threading.Thread(target=run, args=("a", PlainBox)),
        threading.Thread(target=run, args=("b", PlainSibling)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert seen["a"] == {CSS}
    assert seen["b"] == {Path("/app/components/sibling.css")}


def test_on_rendered_fires_once_per_component_not_per_reactive_update():
    with_assets(PlainBox, css=[CSS], js=[JS])
    box = PlainBox()
    with request_scope(session=_accumulating_session()) as session:
        render(box, session)
        render(box, session)
        assert session.css_assets == {CSS}
        assert session.js_assets == {JS}


def test_accumulates_without_any_active_request_scope():
    """render(component, session) — the convention every other pyjinhx test
    uses (see the shared render_session fixture) — must accumulate assets on
    its own, since accumulate_assets reads the session passed to render_level
    rather than the request_scope ContextVar. A session is a valid render
    target whether or not it was ever entered into request_scope()."""
    with_assets(PlainBox, css=[CSS])
    session = _accumulating_session()
    render(PlainBox(), session)
    assert session.css_assets == {CSS}


def test_accumulates_into_the_render_session_even_when_a_different_session_is_the_active_scope():
    """A caller who calls render(component, session_a) while some unrelated
    session_b happens to be the active request_scope must still accumulate
    into session_a — never into whichever session the ContextVar points at."""
    with_assets(PlainBox, css=[CSS])
    target = _accumulating_session()
    other = _accumulating_session()
    with request_scope(session=other):
        render(PlainBox(), target)
    assert target.css_assets == {CSS}
    assert other.css_assets == set()


def test_css_and_js_paths_tracked_distinguishably():
    with_assets(PlainBox, css=[CSS], js=[JS])
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        assert session.css_assets == {CSS}
        assert session.js_assets == {JS}
        assert CSS not in session.js_assets
        assert JS not in session.css_assets


class UnrenderedWidget(BaseComponent):
    """Never instantiated in any test — proves all_assets() is registry-wide."""


class EmptyAssetComponent(BaseComponent):
    """Declares no assets — must contribute nothing to all_assets()."""


UnrenderedWidget.__pjx_descriptor__ = _plain_descriptor(UnrenderedWidget)
EmptyAssetComponent.__pjx_descriptor__ = _plain_descriptor(EmptyAssetComponent)

WIDGET_CSS = Path("/app/components/widget.css")
WIDGET_JS = Path("/app/components/widget.js")


def test_all_assets_returns_sorted_deduped_pairs():
    with_assets(PlainBox, css=[CSS, WIDGET_CSS], js=[JS])
    with_assets(PlainSibling, css=[CSS], js=[JS, WIDGET_JS])
    css, js = all_assets()
    assert css == tuple(sorted(css, key=str))
    assert js == tuple(sorted(js, key=str))
    assert list(css).count(CSS) == 1
    assert list(js).count(JS) == 1
    assert WIDGET_CSS in css
    assert WIDGET_JS in js


def test_all_assets_includes_unrendered_classes():
    with_assets(UnrenderedWidget, css=[WIDGET_CSS], js=[WIDGET_JS])
    css, js = all_assets()
    assert WIDGET_CSS in css
    assert WIDGET_JS in js


def test_all_assets_excludes_classes_without_assets():
    with_assets(PlainBox)
    with_assets(PlainSibling)
    with_assets(UnrenderedWidget)
    with_assets(EmptyAssetComponent)
    css, js = all_assets()
    for path in (CSS, WIDGET_CSS):
        assert path not in css
    for path in (JS, WIDGET_JS):
        assert path not in js


def test_all_assets_does_not_mutate_session_state():
    with_assets(PlainBox, css=[CSS])
    with_assets(PlainSibling, css=[WIDGET_CSS])
    session = _accumulating_session()
    all_assets()
    render(PlainBox(), session)
    all_assets()
    assert session.css_assets == {CSS}
    assert session.js_assets == set()


def test_all_assets_returns_paths_not_strings():
    with_assets(PlainBox, css=[CSS], js=[JS])
    css, js = all_assets()
    assert all(isinstance(path, Path) for path in css)
    assert all(isinstance(path, Path) for path in js)


def test_asset_token_is_a_stable_short_digest_of_the_normalized_path():
    from pyjinhx.assets import asset_token

    token = asset_token(Path("a/../a/style.css"))
    assert token == asset_token(Path("a/style.css"))
    assert len(token) == 16
    assert token.isalnum()


def test_asset_token_differs_per_path():
    from pyjinhx.assets import asset_token

    assert asset_token(Path("a/style.css")) != asset_token(Path("b/style.css"))
