from pathlib import Path

import pytest

from pyjinhx import Renderer
from pyjinhx.reactive import oob_swaps

# Imported via the SFC hook (registers the classes process-wide):
from tests.ui.sfc.sfc_card import SfcCard
from tests.ui.sfc.sfc_counter import SfcCounter, SfcKeys
from tests.ui.sfc.sfc_picked import SfcPicked
from tests.ui.sfc.sfc_inner import SfcInner  # absolute import (validates absolute path)
from tests.ui.sfc.sfc_outer import SfcOuter  # its block does a RELATIVE .pjx import
from tests.ui.sfc.sfc_styled import SfcStyled

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _env():
    Renderer.set_default_environment(str(ROOT))
    yield
    Renderer.set_default_environment(None)


def test_plain_sfc_renders_and_is_file_backed():
    html = SfcCard(title="Hi").render()
    assert "sfc-card" in html
    assert "Hi" in html
    assert SfcCard._pjx_source_path.endswith("sfc_card.pjx")


def test_single_component_with_helper_class():
    # sfc_picked.pjx defines a plain helper class (SfcLabel) alongside the one
    # component — the helper is fine; only one BaseComponent subclass is the
    # component, and it binds the template.
    assert SfcPicked.__name__ == "SfcPicked"
    assert "picked" in SfcPicked(label="picked").render()
    assert SfcPicked._pjx_source_path.endswith("sfc_picked.pjx")


def test_cross_pjx_import_relative_and_absolute():
    # absolute import already resolved at module top (SfcInner)
    assert SfcInner(text="x").render().strip().startswith("<em")
    # sfc_outer's block imported SfcInner via a RELATIVE .pjx import; compose them
    html = SfcOuter(inner=SfcInner(text="deep")).render()
    assert "sfc-outer" in html
    assert "deep" in html  # inner rendered inside outer


def test_reactive_sfc_round_trip():
    counter = SfcCounter.load()
    assert counter.remaining == 3
    rendered = counter.render()
    assert "3 left" in rendered
    assert 'data-pjx-type="SfcCounter"' in rendered

    # mount manifest with a stale hash → dirtying the key must emit a swap
    manifest = [{"id": counter.id, "type": "SfcCounter", "hash": "stale-hash"}]
    swaps = oob_swaps({SfcKeys.WIDGETS}, manifest)
    assert "hx-swap-oob" in swaps
    assert "3 left" in swaps


def test_colocated_assets_are_collected():
    html = SfcStyled(label="styled").render()
    assert "rebeccapurple" in html  # sfc_styled.css inlined
    assert "sfc-styled" in html
