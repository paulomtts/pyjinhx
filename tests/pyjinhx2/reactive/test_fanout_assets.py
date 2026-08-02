"""The asset-delta leg of fan-out: which required assets the client is missing."""

import dataclasses
from pathlib import Path

import pytest

from pyjinhx2.assets import AssetMode, asset_token
from pyjinhx2.reactive.assets import missing_asset_oob, required_asset_paths
from pyjinhx2.reactive.component import ReactiveComponent
from pyjinhx2.reactive.fanout import FanoutCandidate
from pyjinhx2.reactive.keys import MutationKey
from pyjinhx2.session import RenderSession


class Keys(MutationKey):
    WIDGET = "widget"


class AssetWidget(ReactiveComponent, react=(Keys.WIDGET,)):
    """A reactive component whose descriptor is repointed at real asset files."""

    def load(self) -> int:
        return 0


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
    fragment = missing_asset_oob(
        [candidate()], frozenset({asset_token(css)}), session
    )

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
        def load(self) -> int:
            return 0

    bare = dataclasses.replace(candidate(), component_class=Bare)
    assert missing_asset_oob([bare], frozenset(), RenderSession()) == ""


def test_non_inline_modes_emit_nothing(asset_files):
    session = RenderSession()
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.LINK

    assert missing_asset_oob([candidate()], frozenset(), session) == ""
