"""The asset-delta leg of fan-out: which required assets the client is missing."""

import dataclasses
from pathlib import Path
from typing import Any, cast

import pytest

from pyjinhx.assets import AssetMode, asset_token
from pyjinhx.reactive.assets import missing_asset_oob, required_asset_paths
from pyjinhx.reactive.component import ReactiveComponent
from pyjinhx.reactive.fanout import FanoutCandidate
from pyjinhx.reactive.keys import MutationKey
from pyjinhx.segments import RenderedLevel
from pyjinhx.session import RenderSession


class Keys(MutationKey):
    WIDGET = "widget"


class AssetWidget(ReactiveComponent, react=(Keys.WIDGET,)):
    """A reactive component whose descriptor is repointed at real asset files."""

    @classmethod
    def load(cls) -> "AssetWidget":
        return cls()


@pytest.fixture
def asset_files(tmp_path: Path) -> tuple[Path, Path]:
    css = tmp_path / "widget.css"
    css.write_text(".widget{color:red}")
    js = tmp_path / "widget.js"
    js.write_text("window.widget=1;")
    AssetWidget.__pjx_descriptor__ = dataclasses.replace(
        AssetWidget.__pjx_descriptor__, css_paths=(css,), js_paths=(js,)
    )
    return css, js


def candidate(status: str = "dirty") -> FanoutCandidate:
    return FanoutCandidate(
        type_name="asset_widget",
        component_class=AssetWidget,
        instance_id="w1",
        load=None,
        status=status,
        entry={"id": "w1", "type": "asset_widget"},
    )


def test_required_asset_paths_reads_the_candidate_classes_descriptors(asset_files):
    css, js = asset_files
    assert required_asset_paths([candidate()]) == ({css}, {js})


def test_a_missing_candidate_requires_nothing(asset_files):
    assert required_asset_paths([candidate(status="missing")]) == (set(), set())


def test_missing_asset_oob_emits_only_the_tokens_the_client_lacks(asset_files):
    css, js = asset_files
    session = RenderSession()
    fragment = missing_asset_oob([candidate()], frozenset({asset_token(css)}), session)

    assert asset_token(css) not in fragment
    assert (
        f'<script data-pjx-asset="{asset_token(js)}" '
        'hx-swap-oob="beforeend:head">window.widget=1;</script>' in fragment
    )


def test_missing_asset_oob_emits_both_kinds_when_the_client_has_nothing(asset_files):
    css, js = asset_files
    fragment = missing_asset_oob([candidate()], frozenset(), RenderSession())

    assert f'<style data-pjx-asset="{asset_token(css)}"' in fragment
    assert f'<script data-pjx-asset="{asset_token(js)}"' in fragment
    # CSS before JS, so a script that measures layout sees the styled DOM.
    assert fragment.index("<style") < fragment.index("<script")


def test_missing_asset_oob_is_empty_when_the_client_has_everything(asset_files):
    css, js = asset_files
    loaded = frozenset({asset_token(css), asset_token(js)})

    assert missing_asset_oob([candidate()], loaded, RenderSession()) == ""


def test_garbage_tokens_are_treated_as_having_nothing(asset_files):
    css, _ = asset_files
    fragment = missing_asset_oob(
        [candidate()], frozenset({"not-a-real-token"}), RenderSession()
    )

    assert asset_token(css) in fragment


def test_a_class_with_no_assets_is_a_no_op_not_an_error():
    class Bare(ReactiveComponent, react=(Keys.WIDGET,)):
        @classmethod
        def load(cls) -> "Bare":
            return cls()

    bare = dataclasses.replace(candidate(), component_class=Bare)
    assert missing_asset_oob([bare], frozenset(), RenderSession()) == ""


def test_non_inline_modes_emit_nothing(asset_files):
    session = RenderSession()
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.LINK

    assert missing_asset_oob([candidate()], frozenset(), session) == ""


def test_reactive_response_appends_the_asset_fragment_after_the_swaps(
    asset_files, monkeypatch
):
    from pyjinhx import responses as responses_module

    css, _ = asset_files
    # status="clean": a "dirty" FanoutCandidate must carry a real RenderedLevel
    # or oob_swaps() asserts (walk_manifest's contract), and this test only
    # exercises the asset leg, not the swap markup.
    monkeypatch.setattr(
        responses_module,
        "walk_manifest",
        lambda *args, **kwargs: [candidate("clean")],
    )
    session = RenderSession()
    session.pjx_assets = frozenset({"nope"})
    composed = responses_module.compose("", session=session)
    assert isinstance(composed, responses_module.PjxResponse)
    body = str(composed.body)

    assert asset_token(css) in body


def test_reactive_response_omits_the_asset_fragment_when_the_client_has_it(
    asset_files, monkeypatch
):
    from pyjinhx import responses as responses_module

    css, js = asset_files
    monkeypatch.setattr(
        responses_module,
        "walk_manifest",
        lambda *args, **kwargs: [candidate("clean")],
    )
    session = RenderSession()
    session.pjx_assets = frozenset({asset_token(css), asset_token(js)})
    composed = responses_module.compose("", session=session)
    assert isinstance(composed, responses_module.PjxResponse)
    body = str(composed.body)

    assert "data-pjx-asset" not in body


def test_an_assets_only_body_still_says_do_not_swap(asset_files, monkeypatch):
    from pyjinhx import responses as responses_module

    monkeypatch.setattr(
        responses_module,
        "walk_manifest",
        lambda *args, **kwargs: [candidate("clean")],
    )
    session = RenderSession()
    composed = responses_module.compose("", session=session)
    assert isinstance(composed, responses_module.PjxResponse)

    assert "data-pjx-asset" in str(composed.body)
    assert composed.headers["HX-Reswap"] == "none"


def descendant_level(css: Path, js: Path) -> RenderedLevel:
    """A RenderedLevel standing in for a descendant rendered inside the walk."""

    class Descriptor:
        css_paths = (css,)
        js_paths = (js,)

    return RenderedLevel(
        segments=["<div>child</div>"], root_span=(0, 5), descriptor=Descriptor()
    )


def test_a_descendant_rendered_during_the_walk_gets_its_assets_delivered(
    tmp_path, monkeypatch
):
    from pyjinhx import responses as responses_module

    child_css = tmp_path / "child.css"
    child_css.write_text(".child{color:blue}")
    child_js = tmp_path / "child.js"
    child_js.write_text("window.child=1;")
    session = RenderSession()

    def fake_walk(*args, **kwargs):
        # Stands in for a descendant render inside walk_manifest: the walk fires
        # on_rendered for components no top-level candidate names.
        # cast(Any, None), not a bare None: emit_rendered's component parameter
        # is typed BaseComponent, and basedpyright standard mode rejects None
        # there — the existing on_rendered tests use the same cast for the same
        # reason (tests/pyjinhx/test_session.py).
        session.emit_rendered(cast(Any, None), descendant_level(child_css, child_js))
        return [candidate("clean")]

    monkeypatch.setattr(responses_module, "walk_manifest", fake_walk)
    composed = responses_module.compose("", session=session)
    assert isinstance(composed, responses_module.PjxResponse)
    body = str(composed.body)

    assert f'<style data-pjx-asset="{asset_token(child_css)}"' in body
    assert ".child{color:blue}" in body
    assert f'<script data-pjx-asset="{asset_token(child_js)}"' in body
    assert "window.child=1;" in body


def test_link_mode_emits_url_oob_fragments_instead_of_nothing(asset_files):
    css, js = asset_files
    session = RenderSession()
    session.css_mode = AssetMode.LINK
    session.js_mode = AssetMode.LINK
    fragment = missing_asset_oob(
        [candidate()],
        frozenset(),
        session,
        resolver=lambda path: f"/static/{path.name}",
    )

    assert (
        f'<link rel="stylesheet" data-pjx-asset="{asset_token(css)}" '
        'hx-swap-oob="beforeend:head" href="/static/widget.css">' in fragment
    )
    assert (
        f'<script data-pjx-asset="{asset_token(js)}" '
        'hx-swap-oob="beforeend:head" src="/static/widget.js"></script>' in fragment
    )
    # CSS before JS, so a script that measures layout sees the styled DOM.
    assert fragment.index("<link") < fragment.index("<script")


def test_link_mode_skips_the_tokens_the_client_already_reports(asset_files):
    css, js = asset_files
    session = RenderSession()
    session.css_mode = AssetMode.LINK
    session.js_mode = AssetMode.LINK
    fragment = missing_asset_oob(
        [candidate()],
        frozenset({asset_token(css)}),
        session,
        resolver=lambda path: f"/static/{path.name}",
    )

    assert asset_token(css) not in fragment
    assert asset_token(js) in fragment


def test_compose_threads_the_resolver_into_the_link_mode_fragments(
    asset_files, monkeypatch
):
    from pyjinhx import responses as responses_module

    css, js = asset_files
    monkeypatch.setattr(
        responses_module,
        "walk_manifest",
        lambda *args, **kwargs: [candidate("clean")],
    )
    session = RenderSession()
    session.css_mode = AssetMode.LINK
    session.js_mode = AssetMode.LINK
    composed = responses_module.compose(
        "", session=session, resolver=lambda path: f"/static/{path.name}"
    )
    assert isinstance(composed, responses_module.PjxResponse)
    body = str(composed.body)

    assert (
        f'<link rel="stylesheet" data-pjx-asset="{asset_token(css)}" '
        'hx-swap-oob="beforeend:head" href="/static/widget.css">' in body
    )
    assert (
        f'<script data-pjx-asset="{asset_token(js)}" '
        'hx-swap-oob="beforeend:head" src="/static/widget.js"></script>' in body
    )


def test_none_mode_emits_nothing_even_when_the_walk_accumulated_assets(
    tmp_path, monkeypatch
):
    from pyjinhx import responses as responses_module

    child_css = tmp_path / "child.css"
    child_css.write_text(".child{color:blue}")
    child_js = tmp_path / "child.js"
    child_js.write_text("window.child=1;")
    session = RenderSession()
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.NONE

    def fake_walk(*args, **kwargs):
        # cast(Any, None), not a bare None: emit_rendered's component parameter
        # is typed BaseComponent, and basedpyright standard mode rejects None
        # there — the existing on_rendered tests use the same cast for the same
        # reason (tests/pyjinhx/test_session.py).
        session.emit_rendered(cast(Any, None), descendant_level(child_css, child_js))
        return [candidate("clean")]

    monkeypatch.setattr(responses_module, "walk_manifest", fake_walk)
    composed = responses_module.compose("", session=session)
    assert isinstance(composed, responses_module.PjxResponse)

    assert "data-pjx-asset" not in str(composed.body)
