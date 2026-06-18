# tests/84_all_assets_test.py
import os

import pyjinhx.builtins
from pyjinhx.assets import hashed_filename, resolver_with_hash
from pyjinhx.finder import Finder


def test_all_assets_returns_ordered_pairs():
    root = os.path.join(os.path.dirname(pyjinhx.builtins.__file__), "ui")
    css, js = Finder(root).all_assets()
    assert all(p.endswith(".css") for p in css)
    assert all(p.endswith(".js") for p in js)
    assert css == sorted(css) and js == sorted(js)
    assert any(p.endswith("pjx_modal/pjx-modal.css") for p in css)
    assert any(p.endswith("pjx_modal/pjx-modal.js") for p in js)


def test_layout_asset_tags_lists_all_files():
    finder = Finder(root="tests/ui")

    def resolver(path: str) -> str:
        return f"/static/{os.path.basename(path)}"

    tags = str(finder.layout_asset_tags(resolver=resolver))

    assert "unified-component.css" in tags
    assert "unified-component.js" in tags
    assert tags.index("<link") < tags.index("<script")


def test_hashed_filename_is_stable():
    path = "tests/ui/unified-component.js"
    first = hashed_filename(path)
    second = hashed_filename(path)
    assert first == second
    assert first.endswith(".js")
    assert "." in first.removesuffix(".js")


def test_resolver_with_hash_embeds_digest():
    resolver = resolver_with_hash("/static/components", "tests/ui")
    url = resolver(os.path.abspath("tests/ui/unified-component.js"))
    assert url.startswith("/static/components/")
    assert url.count(".") >= 2
