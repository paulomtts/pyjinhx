"""Golden-HTML snapshots for every builtin.

Regenerate intentionally with:  PJX_GOLDEN_UPDATE=1 uv run pytest tests/unit/test_golden_builtins.py -q
Auto-generated ids (px-<n>) are masked so snapshots are stable.
"""
import os
import re
from pathlib import Path

import pytest

from pyjinhx.assets import AssetMode
from pyjinhx.renderer import Renderer

import pyjinhx.builtins as b

GOLDEN_DIR = Path(__file__).parent / "golden"

CASES = [
    ("alert_default", lambda: b.Alert(id="g", body="Saved.")),
    ("alert_dismissible", lambda: b.Alert(id="g", title="Heads up", body="x", dismissible=True, variant="warning")),
    ("avatar_initials", lambda: b.Avatar(id="g", initials="PM")),
    ("avatar_image", lambda: b.Avatar(id="g", src="/u.png", alt="User", size="lg")),
    ("avatar_stack", lambda: b.AvatarStack(id="g", avatars=[b.Avatar(id="g-a", initials="AB")], extra_count=2)),
    ("badge_default", lambda: b.Badge(id="g", label="New")),
    ("breadcrumb", lambda: b.Breadcrumb(id="g", items=[("Home", "/"), ("Here", None)])),
    ("card_full", lambda: b.Card(id="g", title="T", body="B", footer="F")),
    ("confirm_dialog", lambda: b.ConfirmDialog(id="g")),
    ("divider_labeled", lambda: b.Divider(id="g", label="or")),
    ("drawer", lambda: b.Drawer(id="g", title="T", body="B", footer="F")),
    ("dropdown", lambda: b.Dropdown(id="g", trigger="Menu", items=["<a href='/x'>X</a>"])),
    ("empty_state", lambda: b.EmptyState(id="g", title="Nothing", description="D", action="<button>A</button>")),
    ("lazy_panel", lambda: b.LazyPanel(id="g", url="/load")),
    ("region_loader", lambda: b.RegionLoader(id="g")),
    ("modal", lambda: b.Modal(id="g", title="T", body="B", footer="F")),
    ("notification", lambda: b.Notification(id="g", content="Hi", corner="bottom-right", timeout=0)),
    ("page_loader", lambda: b.PageLoader(id="g")),
    ("panel", lambda: b.Panel(id="g", panels={"a": "<p>A</p>", "b": "<p>B</p>"})),
    ("panel_trigger", lambda: b.PanelTrigger(id="g", panel_id="host", panel="a", content="Tab A")),
    ("popover_compound", lambda: b.Popover(id="g", content=(
        str(b.PopoverTrigger(id="g-t", content="Open", role="menu").render())
        + str(b.PopoverPanel(id="g-p", content="Items", role="menu").render())
    ))),
    ("progress_determinate", lambda: b.Progress(id="g", value=40, label="Upload")),
    ("progress_indeterminate", lambda: b.Progress(id="g")),
    ("prompt_dialog", lambda: b.PromptDialog(id="g", input_label="Name")),
    ("skeleton_text", lambda: b.Skeleton(id="g", lines=2)),
    ("spinner", lambda: b.Spinner(id="g")),
    ("tab_group", lambda: b.TabGroup(id="g", tabs={"One": "<p>1</p>", "Two": "<p>2</p>"})),
    ("toast_host", lambda: b.ToastHost(id="g")),
    ("tooltip", lambda: b.Tooltip(id="g", trigger="?", tip="Help")),
    ("chip_input", lambda: b.ChipInput(id="g", name="tags", values=["alpha", "beta"])),
    ("form_field", lambda: b.FormField(id="g", label="Email", for_id="g-in", content="<input id='g-in'>", error="Required")),
    ("toggle_switch", lambda: b.ToggleSwitch(id="g", name="active", checked=True, label="Active")),
    ("segmented_control", lambda: b.SegmentedControl(id="g", name="view", options=[("list", "List"), ("grid", "Grid")], selected="list")),
    ("password_input", lambda: b.PasswordInput(id="g")),
]


def _normalize(html: str) -> str:
    html = re.sub(r"px-\d+", "px-AUTO", html)
    return html.strip() + "\n"


@pytest.fixture()
def _markup_only_renderer():
    prev_js, prev_css = Renderer._default_js_mode, Renderer._default_css_mode
    Renderer.set_default_js_mode(AssetMode.NONE)
    Renderer.set_default_css_mode(AssetMode.NONE)
    yield
    Renderer.set_default_js_mode(prev_js)
    Renderer.set_default_css_mode(prev_css)


@pytest.mark.parametrize("name,factory", CASES, ids=[c[0] for c in CASES])
def test_golden(name, factory, _markup_only_renderer):
    rendered = _normalize(str(factory().render()))
    path = GOLDEN_DIR / f"{name}.html"
    if os.environ.get("PJX_GOLDEN_UPDATE") == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        path.write_text(rendered)
    assert path.exists(), f"missing snapshot {path.name}; run with PJX_GOLDEN_UPDATE=1"
    assert rendered == path.read_text(), (
        f"golden mismatch for {name}; if intentional, regenerate with PJX_GOLDEN_UPDATE=1 and review the diff"
    )
