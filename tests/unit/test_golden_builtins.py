"""Golden-HTML snapshots for every builtin.

Regenerate intentionally with:  PJX_GOLDEN_UPDATE=1 uv run pytest tests/unit/test_golden_builtins.py -q
Auto-generated ids (pjx-<n>) are masked so snapshots are stable.
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
    ("alert_default", lambda: b.PJXAlert(id="g", body="Saved.")),
    ("alert_dismissible", lambda: b.PJXAlert(id="g", title="Heads up", body="x", dismissible=True, variant="warning")),
    ("avatar_initials", lambda: b.PJXAvatar(id="g", initials="PM")),
    ("avatar_image", lambda: b.PJXAvatar(id="g", src="/u.png", alt="User", size="lg")),
    ("avatar_stack", lambda: b.PJXAvatarStack(id="g", avatars=[b.PJXAvatar(id="g-a", initials="AB")], extra_count=2)),
    ("badge_default", lambda: b.PJXBadge(id="g", label="New")),
    ("breadcrumb", lambda: b.PJXBreadcrumb(id="g", items=[("Home", "/"), ("Here", None)])),
    ("card_full", lambda: b.PJXCard(id="g", title="T", body="B", footer="F")),
    ("confirm_dialog", lambda: b.PJXConfirmDialog(id="g")),
    ("divider_labeled", lambda: b.PJXDivider(id="g", label="or")),
    ("drawer", lambda: b.PJXDrawer(id="g", title="T", body="B", footer="F")),
    ("dropdown", lambda: b.PJXDropdown(id="g", trigger="Menu", items=["<a href='/x'>X</a>"])),
    ("empty_state", lambda: b.PJXEmptyState(id="g", title="Nothing", description="D", action="<button>A</button>")),
    ("lazy_panel", lambda: b.PJXLazyPanel(id="g", url="/load")),
    ("region_loader", lambda: b.PJXRegionLoader(id="g")),
    ("modal", lambda: b.PJXModal(id="g", title="T", body="B", footer="F")),
    ("notification", lambda: b.PJXNotification(id="g", content="Hi", corner="bottom-right", timeout=0)),
    ("page_loader", lambda: b.PJXPageLoader(id="g")),
    ("panel", lambda: b.PJXPanel(id="g", panels={"a": "<p>A</p>", "b": "<p>B</p>"})),
    ("panel_trigger", lambda: b.PJXPanelTrigger(id="g", panel_id="host", panel="a", content="Tab A")),
    ("popover_compound", lambda: b.PJXPopover(id="g", content=(
        str(b.PJXPopoverTrigger(id="g-t", content="Open", role="menu").render())
        + str(b.PJXPopoverPanel(id="g-p", content="Items", role="menu").render())
    ))),
    ("progress_determinate", lambda: b.PJXProgress(id="g", value=40, label="Upload")),
    ("progress_indeterminate", lambda: b.PJXProgress(id="g")),
    ("prompt_dialog", lambda: b.PJXPromptDialog(id="g", input_label="Name")),
    ("skeleton_text", lambda: b.PJXSkeleton(id="g", lines=2)),
    ("spinner", lambda: b.PJXSpinner(id="g")),
    ("tab_group", lambda: b.PJXTabGroup(id="g", tabs={"One": "<p>1</p>", "Two": "<p>2</p>"})),
    ("toast_host", lambda: b.PJXToastHost(id="g")),
    ("tooltip", lambda: b.PJXTooltip(id="g", trigger="?", tip="Help")),
    ("chip_input", lambda: b.PJXChipInput(id="g", name="tags", values=["alpha", "beta"])),
    ("form_field", lambda: b.PJXFormField(id="g", label="Email", for_id="g-in", content="<input id='g-in'>", error="Required")),
    ("toggle_switch", lambda: b.PJXToggleSwitch(id="g", name="active", checked=True, label="Active")),
    ("segmented_control", lambda: b.PJXSegmentedControl(id="g", name="view", options=[("list", "List"), ("grid", "Grid")], selected="list")),
    ("password_input", lambda: b.PJXPasswordInput(id="g")),
    ("icon_plus", lambda: b.PJXIcon(id="g", name="plus")),
    ("icon_labeled", lambda: b.PJXIcon(id="g", name="search", label="Search", size=20)),
    ("button_default", lambda: b.PJXButton(id="g", center="Save")),
    ("button_loading", lambda: b.PJXButton(id="g", center="Save", loading=True, variant="primary")),
    ("accordion_open", lambda: b.PJXAccordion(id="g", content=str(b.PJXAccordionTrigger(id="g-t", content="Today").render()) + str(b.PJXAccordionContent(id="g-c", content="<p>x</p>").render()))),
    ("accordion_grouped_closed", lambda: b.PJXAccordion(id="g", open=False, group="nav", content=str(b.PJXAccordionTrigger(id="g-t", content="Older").render()) + str(b.PJXAccordionContent(id="g-c", content="<p>y</p>").render()))),
    ("accordion_trigger", lambda: b.PJXAccordionTrigger(id="g", content="Section")),
    ("accordion_content", lambda: b.PJXAccordionContent(id="g", content="<p>body</p>")),
    ("accordion_group_multi", lambda: b.PJXAccordionGroup(id="g", content=str(b.PJXAccordion(id="g-a", content=str(b.PJXAccordionTrigger(id="g-at", content="A").render()) + str(b.PJXAccordionContent(id="g-ac", content="<p>x</p>").render())).render()) + str(b.PJXAccordion(id="g-b", open=False, content=str(b.PJXAccordionTrigger(id="g-bt", content="B").render()) + str(b.PJXAccordionContent(id="g-bc", content="<p>y</p>").render())).render()))),
    ("accordion_group_exclusive", lambda: b.PJXAccordionGroup(id="g", mode="exclusive", gap="0.5rem", content=str(b.PJXAccordion(id="g-a", content=str(b.PJXAccordionTrigger(id="g-at", content="A").render()) + str(b.PJXAccordionContent(id="g-ac", content="<p>x</p>").render())).render()) + str(b.PJXAccordion(id="g-b", open=False, content=str(b.PJXAccordionTrigger(id="g-bt", content="B").render()) + str(b.PJXAccordionContent(id="g-bc", content="<p>y</p>").render())).render()))),
    ("accordion_group_default_open_first", lambda: b.PJXAccordionGroup(id="g", default_open="first", content=str(b.PJXAccordion(id="g-a", open=False, content=str(b.PJXAccordionTrigger(id="g-at", content="A").render()) + str(b.PJXAccordionContent(id="g-ac", content="<p>x</p>").render())).render()) + str(b.PJXAccordion(id="g-b", open=False, content=str(b.PJXAccordionTrigger(id="g-bt", content="B").render()) + str(b.PJXAccordionContent(id="g-bc", content="<p>y</p>").render())).render()))),
]


def _normalize(html: str) -> str:
    html = re.sub(r"pjx-\d+", "pjx-AUTO", html)
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
