"""The docs demo registry stays complete and every demo renders (ported from v0.x for #540)."""

import re
import sys
from pathlib import Path

import pytest

import pyjinhx.builtins  # noqa: F401

DOCS = Path(__file__).resolve().parents[2] / "docs"
sys.path.insert(0, str(DOCS))

import hooks
from demos import DEMOS


class FakeFile:
    src_path = "components.md"


class FakePage:
    file = FakeFile()
    url = "components/"


def test_marker_becomes_iframe():
    out = hooks.on_page_markdown(
        "intro\n\n<!-- demo: PJXBadge -->\n\nafter",
        page=FakePage(),
        config={},
        files=None,
    )
    assert '<iframe src="../demos/pjx-badge.html"' in out
    assert "```python" not in out  # the marker no longer emits a code block


def test_unknown_demo_fails_build():
    with pytest.raises(ValueError, match="Nope"):
        hooks.on_page_markdown(
            "<!-- demo: Nope -->", page=FakePage(), config={}, files=None
        )


def test_post_build_writes_selfcontained_pages(tmp_path):
    hooks.on_post_build({"site_dir": str(tmp_path)})
    page = (tmp_path / "demos" / "pjx-badge.html").read_text()
    assert "pjx-badge" in page
    assert "demo-base.css" in page
    assert (tmp_path / "demos" / "demo-base.css").exists()


def test_every_factory_renders():
    from pyjinhx.session import request_scope

    for name, (factory, height) in DEMOS.items():
        with request_scope(template_dir="/"):
            markup = hooks.demo_markup(factory())
        assert markup.strip(), name
        assert isinstance(height, int), name


def _descriptor_css_text(cls) -> list[str]:
    """The on-disk text of every stylesheet the class's descriptor points at."""
    return [Path(p).read_text() for p in cls.__pjx_descriptor__.css_paths]


def test_post_build_inlines_component_css(tmp_path):
    from pyjinhx.builtins.ui.pjx_button import PJXButton

    hooks.on_post_build({"site_dir": str(tmp_path)})
    page = (tmp_path / "demos" / "pjx-button.html").read_text()
    css_texts = _descriptor_css_text(PJXButton)
    assert css_texts, "PJXButton is expected to carry at least one stylesheet"
    for text in css_texts:
        assert f"<style>{text}</style>" in page


def test_gallery_page_features_every_demo():
    """components.md must feature every builtin that has a demo (DEMOS key).

    The page is hand-curated (one `## Name` section + `<!-- demo: Name -->` per
    builtin), so a new builtin's demo could be missing from it. This guards it.
    """
    page = (DOCS / "components.md").read_text(encoding="utf-8")
    featured = set(re.findall(r"<!--\s*demo:\s*([A-Za-z]+)\s*-->", page))
    missing = sorted(set(DEMOS) - featured)
    assert not missing, (
        "docs/components.md is missing a `<!-- demo: Name -->` for these demo'd "
        f"builtins: {missing}"
    )


def test_demo_markup_wraps_in_stage():
    assert hooks.demo_markup("<b>x</b>") == '<div class="pjx-demo-stage"><b>x</b></div>'
    row = hooks.demo_markup(["<b>x</b>", "<i>y</i>"])
    assert 'class="pjx-demo-stage pjx-demo-stage--row"' in row
    assert "<b>x</b>" in row and "<i>y</i>" in row


def test_all_demo_factories_render(tmp_path):
    from pyjinhx.session import request_scope

    for name, (factory, _h) in DEMOS.items():
        with request_scope(template_dir="/"):
            markup = hooks.demo_markup(factory())
        assert "pjx-demo-stage" in markup, name
        assert markup.strip(), name
