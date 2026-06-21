"""The docs demo registry stays complete and every demo renders."""

import sys
from pathlib import Path

import pytest
import pyjinhx.builtins
from pyjinhx.builtins import PJXBadge  # noqa: E402

DOCS = Path(__file__).resolve().parents[2] / "docs"
sys.path.insert(0, str(DOCS))

from demos import DEMOS  # noqa: E402
import hooks  # noqa: E402


class FakeFile:
    src_path = "guide/builtins.md"


class FakePage:
    file = FakeFile()
    url = "guide/builtins/"


def test_marker_becomes_iframe_and_source():
    out = hooks.on_page_markdown(
        "intro\n\n<!-- demo: PJXBadge -->\n\nafter", page=FakePage(), config={}, files=None
    )
    assert '<iframe src="../../demos/pjx-badge.html"' in out
    assert "```python" in out
    assert 'PJXBadge(label="Active"' in out
    assert "def " not in out
    assert "return " not in out
    assert "<!-- demo:" not in out


def test_unknown_demo_fails_build():
    with pytest.raises(ValueError, match="Nope"):
        hooks.on_page_markdown("<!-- demo: Nope -->", page=FakePage(), config={}, files=None)


def test_post_build_writes_selfcontained_pages(tmp_path):
    hooks.on_post_build({"site_dir": str(tmp_path)})
    page = (tmp_path / "demos" / "pjx-badge.html").read_text()
    assert "pjx-badge" in page
    assert "demo-base.css" in page
    assert (tmp_path / "demos" / "demo-base.css").exists()


def test_every_factory_renders():
    for name, (factory, height) in DEMOS.items():
        markup = hooks.demo_markup(factory())
        assert markup.strip(), name
        assert isinstance(height, int), name


def test_registry_covers_all_builtins():
    folded = {
        "PJXAccordionContent",
        "PJXAccordionTrigger",
        "PJXLazyPanel",
        "PJXPanelTrigger",
        "PJXPopoverTrigger",
        "PJXPopoverPanel",
        "PJXCardHeader",
        "PJXCardBody",
        "PJXCardFooter",
        "PJXModalHeader",
        "PJXModalBody",
        "PJXModalFooter",
        "PJXDrawerHeader",
        "PJXDrawerBody",
        "PJXDrawerFooter",
        "PJXTooltipContent",
        "PJXTooltipTrigger",
    }
    assert set(DEMOS) == set(pyjinhx.builtins.__all__) - folded


def test_first_variation_source_picks_first_list_element():
    def f():
        return [
            PJXBadge(label="A", color="brand").render(),
            PJXBadge(label="B", color="error").render(),
        ]
    assert hooks.first_variation_source(f) == 'PJXBadge(label="A", color="brand").render()'


def test_first_variation_source_single_expression():
    def f():
        return PJXBadge(label="A").render()
    assert hooks.first_variation_source(f) == 'PJXBadge(label="A").render()'


def test_demo_markup_wraps_in_stage():
    assert hooks.demo_markup("<b>x</b>") == '<div class="pjx-demo-stage"><b>x</b></div>'
    row = hooks.demo_markup(["<b>x</b>", "<i>y</i>"])
    assert 'class="pjx-demo-stage pjx-demo-stage--row"' in row
    assert "<b>x</b>" in row and "<i>y</i>" in row


def test_all_demo_factories_render(tmp_path):
    from pyjinhx import Registry, Renderer
    Renderer.set_default_environment(str(tmp_path))
    for name, (factory, _h) in DEMOS.items():
        with Registry.request_scope():
            markup = hooks.demo_markup(factory())
        assert "pjx-demo-stage" in markup, name
        assert markup.strip(), name
