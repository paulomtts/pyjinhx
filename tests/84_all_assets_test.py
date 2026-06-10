# tests/84_all_assets_test.py
import os

import pyjinhx.builtins
from pyjinhx.finder import Finder


def test_all_assets_returns_ordered_pairs():
    root = os.path.join(os.path.dirname(pyjinhx.builtins.__file__), "ui")
    css, js = Finder(root).all_assets()
    assert all(p.endswith(".css") for p in css)
    assert all(p.endswith(".js") for p in js)
    assert css == sorted(css) and js == sorted(js)
    assert any(p.endswith("modal/modal.css") for p in css)
    assert any(p.endswith("modal/modal.js") for p in js)
