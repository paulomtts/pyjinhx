"""The docs demo registry stays complete and every demo renders."""

import sys
from pathlib import Path

import pytest

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
        "intro\n\n<!-- demo: Badge -->\n\nafter", page=FakePage(), config={}, files=None
    )
    assert '<iframe src="../../demos/badge.html"' in out
    assert "```python" in out
    assert "def badge" in out
    assert "<!-- demo:" not in out


def test_unknown_demo_fails_build():
    with pytest.raises(ValueError, match="Nope"):
        hooks.on_page_markdown("<!-- demo: Nope -->", page=FakePage(), config={}, files=None)


def test_post_build_writes_selfcontained_pages(tmp_path):
    hooks.on_post_build({"site_dir": str(tmp_path)})
    page = (tmp_path / "demos" / "badge.html").read_text()
    assert "px-badge" in page
    assert "demo-base.css" in page
    assert (tmp_path / "demos" / "demo-base.css").exists()


def test_every_factory_renders():
    for name, (factory, height) in DEMOS.items():
        markup = hooks.demo_markup(factory())
        assert markup.strip(), name
        assert isinstance(height, int), name


def test_registry_covers_all_builtins():
    import pyjinhx.builtins as builtins

    folded = {"LazyPanel", "PanelTrigger", "PopoverTrigger", "PopoverPanel"}
    assert set(DEMOS) == set(builtins.__all__) - folded
