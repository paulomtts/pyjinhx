"""The docs demo registry stays complete and every demo renders."""

import sys
from pathlib import Path

import pytest
import pyjinhx.builtins

DOCS = Path(__file__).resolve().parents[2] / "docs"
sys.path.insert(0, str(DOCS))

from demos import DEMOS  # noqa: E402
import hooks  # noqa: E402


class FakeFile:
    src_path = "guide/builtins.md"


class FakePage:
    file = FakeFile()
    url = "guide/builtins/"


def test_marker_becomes_iframe():
    out = hooks.on_page_markdown(
        "intro\n\n<!-- demo: PJXBadge -->\n\nafter", page=FakePage(), config={}, files=None
    )
    assert '<iframe src="../../demos/pjx-badge.html"' in out
    assert "```python" not in out  # the marker no longer emits a code block


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
        "PJXResizableHandle",
        "PJXResizablePanel",
        "PJXTooltipContent",
        "PJXTooltipTrigger",
        "PJXTab",
        "PJXTabList",
        "PJXTabPanel",
        "PJXTableHead",
        "PJXTableBody",
        "PJXTableRow",
        "PJXTableHeaderCell",
        "PJXTableCell",
    }
    assert set(DEMOS) == set(pyjinhx.builtins.__all__) - folded


def test_gallery_page_features_every_demo():
    """docs/gallery.md must feature every builtin that has a demo (DEMOS key).

    The gallery page is hand-curated (one section + `<!-- demo: Name -->` per
    builtin), so a new builtin's demo can render in the guide yet be missing from
    the gallery — exactly what happened with PJXResizableGroup. This guards it.
    """
    import re

    gallery = (DOCS / "gallery.md").read_text(encoding="utf-8")
    featured = set(re.findall(r"<!--\s*demo:\s*([A-Za-z]+)\s*-->", gallery))
    missing = sorted(set(DEMOS) - featured)
    assert not missing, (
        "docs/gallery.md is missing a section for these demo'd builtins — add a "
        "`### [Name](guide/builtins.md#name)` + `<!-- demo: Name -->` for each: "
        f"{missing}"
    )


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
