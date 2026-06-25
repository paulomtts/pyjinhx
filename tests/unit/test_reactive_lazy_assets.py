"""#184 (reopen) — a reactive component rendered as a lazy fragment must deliver
its own not-yet-loaded builtin assets through the OOB ``<head>`` channel.

The reactive primary render used ``emit_assets=False`` and relied on ``_finish_with_oob``
for asset delivery — but that path only emits assets for *dirtied non-primary*
regions, so a reactive component's *own* assets fell through when it was rendered
in a reactive context (a non-empty mounted manifest) with no pending mutations —
exactly a lazy-loaded reactive fragment. nori's reactive ``TableWorkbench`` lazy
fragment hit this: its nested ``PJXBreadcrumb`` CSS was delivered neither inline nor
OOB, so the breadcrumb rendered unstyled. The primary now emits via the same
``inject_assets`` OOB path the non-reactive lazy render uses (#183).
"""

import os

from pyjinhx.assets import asset_token
from pyjinhx.client import PJX_ASSETS_HEADER
from pyjinhx.finder import Finder
from pyjinhx.builtins import PJXBreadcrumb
from tests.reactive_test_support import reactive_client
from tests.ui.reactive.breadcrumb_panel import BreadcrumbPanel

_BC_DIR = Finder.get_class_directory(PJXBreadcrumb)
_BC_TOKEN = asset_token(os.path.join(_BC_DIR, "pjx-breadcrumb.css"))

# A non-empty manifest (some other mounted reactive region) makes the request a
# reactive context — the condition that triggered the bug. The lazy panel itself
# is fresh (not yet mounted), and no mutation is pending.
_MANIFEST = [{"id": "other", "type": "ReactiveCounter", "hash": "h"}]


def test_lazy_reactive_render_delivers_nested_builtin_oob():
    """The reactive fragment ships its breadcrumb CSS as an OOB head injection."""
    with reactive_client(_MANIFEST):
        out = str(BreadcrumbPanel.render("p1"))

    assert 'data-pjx-id="breadcrumb-panel-p1"' in out  # the primary rendered
    # The breadcrumb CSS is delivered, and as an OOB head injection (not inline).
    assert (
        f'<style data-pjx-asset="{_BC_TOKEN}" hx-swap-oob="beforeend:head">' in out
    ), "reactive lazy fragment did not deliver its nested builtin CSS OOB"
    assert f'<style data-pjx-asset="{_BC_TOKEN}">' not in out, "must be OOB, not inline"


def test_lazy_reactive_render_dedups_already_loaded_builtin():
    """When the client already has the breadcrumb CSS, it is not re-delivered."""
    with reactive_client(
        _MANIFEST, extra_headers={PJX_ASSETS_HEADER: f'["{_BC_TOKEN}"]'}
    ):
        out = str(BreadcrumbPanel.render("p1"))

    assert 'data-pjx-id="breadcrumb-panel-p1"' in out
    assert _BC_TOKEN not in out, "already-loaded asset should be deduped away"
