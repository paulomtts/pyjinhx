from __future__ import annotations

import asyncio
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from pyjinhx import BaseComponent, Renderer
from pyjinhx.builtins import (
    PJXAlert,
    PJXAvatar,
    PJXBadge,
    PJXBreadcrumb,
    PJXCard,
    PJXDivider,
    PJXDrawer,
    PJXDropdown,
    PJXEmptyState,
    PJXRegionLoader,
    PJXModal,
    PJXNotification,
    PJXPanel,
    PJXPanelTrigger,
    PJXPopover,
    PJXPopoverPanel,
    PJXPopoverTrigger,
    PJXProgress,
    PJXSkeleton,
    PJXSpinner,
    PJXTabGroup,
    PJXTooltip,
)

DEFAULT_GALLERY_PORT = 9000

_GALLERY_DIR = Path(__file__).resolve().parent

_SHOWCASE_TEMPLATE = """
<div class="builtins-gallery">
<h2>Badge</h2>
<section class="demo-row">
{{ badge }}
</section>

<h2>Modal</h2>
<section class="demo-stack">
{{ modal }}
<button type="button" class="demo-btn" data-pjx-open="g-modal">Open modal</button>
</section>

<h2>Notification</h2>
<section class="demo-stack">
{{ notification }}
<button type="button" class="demo-btn" onclick="pjx.notification.show('g-toast')">Show notification</button>
</section>

<h2>Popover</h2>
<section class="demo-row">
{{ popover }}
</section>

<h2>Region loader</h2>
<section>
<div style="position:relative;min-height:100px;padding:1rem;border:1px dashed var(--border);border-radius:var(--radius-md);">
{{ region_loader }}
<p style="margin:0;color:var(--text-muted);font-size:var(--font-size-sm);">Parent is position: relative</p>
</div>
<div class="demo-row" style="margin-top:0.75rem;">
<button type="button" class="demo-btn" onclick="pjx.loader.region.show('g-overlay')">Show overlay</button>
<button type="button" class="demo-btn" onclick="pjx.loader.region.hide('g-overlay')">Hide overlay</button>
</div>
</section>

<h2>Tooltip</h2>
<section class="demo-row">
{{ tooltip }}
</section>

<h2>Alert</h2>
<section class="demo-stack">
{{ alert }}
</section>

<h2>Dropdown</h2>
<section class="demo-row">
{{ dropdown }}
</section>

<h2>Drawer</h2>
<section class="demo-stack">
{{ drawer }}
<button type="button" class="demo-btn" data-pjx-open="g-drawer">Open drawer</button>
</section>

<h2>Progress</h2>
<section class="demo-stack">
{{ progress_determinate }}
{{ progress_indeterminate }}
</section>

<h2>Skeleton</h2>
<section class="demo-stack">
{{ skeleton_text }}
<div style="max-width:8rem">{{ skeleton_circle }}</div>
{{ skeleton_rect }}
</section>

<h2>Empty state</h2>
<section>
{{ empty_state }}
</section>

<h2>Divider</h2>
<section class="demo-stack">
{{ divider_horizontal }}
<p style="margin:0;font-size:var(--font-size-sm);color:var(--text-muted);">Plain horizontal rule</p>
{{ divider_labeled }}
</section>

<h2>Spinner</h2>
<section class="demo-row">
{{ spinner_small }}
{{ spinner_medium }}
{{ spinner_large }}
</section>

<h2>Avatar</h2>
<section class="demo-row">
{{ avatar_image }}
{{ avatar_initials }}
</section>

<h2>Card</h2>
<section class="demo-stack">
{{ card }}
</section>

<h2>Breadcrumb</h2>
<section>
{{ breadcrumb }}
</section>

<h2>Tab group</h2>
<section>
{{ tab_group }}
</section>

<h2>Panel (distributed triggers)</h2>
<section class="demo-stack">
<p style="margin:0;font-size:var(--font-size-sm);color:var(--text-muted);">Triggers are separate from the host. Beta uses HTMX SSE (~2.5s per tick): stay on Alpha, wait a few ticks, then open Beta — the hidden slot still receives events.</p>
<div class="demo-row">
{{ panel_trigger_alpha }}
{{ panel_trigger_beta }}
</div>
{{ panel_host }}
</section>
</div>
"""


class BuiltinsGalleryPage(BaseComponent):
    badge: PJXBadge
    modal: PJXModal
    notification: PJXNotification
    popover: PJXPopover
    region_loader: PJXRegionLoader
    tooltip: PJXTooltip
    alert: PJXAlert
    dropdown: PJXDropdown
    drawer: PJXDrawer
    progress_determinate: PJXProgress
    progress_indeterminate: PJXProgress
    skeleton_text: PJXSkeleton
    skeleton_circle: PJXSkeleton
    skeleton_rect: PJXSkeleton
    empty_state: PJXEmptyState
    divider_horizontal: PJXDivider
    divider_labeled: PJXDivider
    spinner_small: PJXSpinner
    spinner_medium: PJXSpinner
    spinner_large: PJXSpinner
    avatar_image: PJXAvatar
    avatar_initials: PJXAvatar
    card: PJXCard
    breadcrumb: PJXBreadcrumb
    tab_group: PJXTabGroup
    panel_trigger_alpha: PJXPanelTrigger
    panel_trigger_beta: PJXPanelTrigger
    panel_host: PJXPanel

    def render(self) -> str:
        return str(self._render(source=_SHOWCASE_TEMPLATE.strip()))


@lru_cache(maxsize=1)
def _gallery_inner_html() -> str:
    tmp = tempfile.mkdtemp(prefix="pyjinhx-gallery-")
    Renderer.set_default_environment(tmp)
    Renderer.get_default_renderer(auto_id=False)
    gallery_page = BuiltinsGalleryPage(
        id="builtins-gallery",
        badge=PJXBadge(id="g-badge", label="Beta", color="brand", shape="md"),
        modal=PJXModal(
            id="g-modal",
            title="Demo modal",
            body="Modal body content from the gallery.",
        ),
        notification=PJXNotification(
            id="g-toast",
            content="Toast message",
            corner="top-right",
            timeout=0,
        ),
        popover=PJXPopover(
            id="g-pop",
            content=(
                str(PJXPopoverTrigger(id="g-pop-t", content="Open popover").render())
                + str(PJXPopoverPanel(id="g-pop-p", content="Popover details appear on click.").render())
            ),
        ),
        region_loader=PJXRegionLoader(id="g-overlay"),
        tooltip=PJXTooltip(
            id="g-tip",
            trigger="Focus or hover",
            tip="Tooltip copy",
            placement="top",
        ),
        alert=PJXAlert(
            id="g-alert",
            variant="info",
            title="Heads up",
            body="This is an inline alert.",
        ),
        dropdown=PJXDropdown(
            id="g-drop",
            trigger="Options",
            items=['<a role="menuitem" href="#">First</a>', '<a role="menuitem" href="#">Second</a>'],
        ),
        drawer=PJXDrawer(
            id="g-drawer",
            side="right",
            title="Drawer",
            body="Side panel content.",
        ),
        progress_determinate=PJXProgress(
            id="g-prog-det",
            value=62,
            max=100,
            label="Determinate",
        ),
        progress_indeterminate=PJXProgress(
            id="g-prog-ind",
            max=100,
            label="Indeterminate",
        ),
        skeleton_text=PJXSkeleton(id="g-skel-text", variant="text", lines=3),
        skeleton_circle=PJXSkeleton(id="g-skel-circle", variant="circle"),
        skeleton_rect=PJXSkeleton(id="g-skel-rect", variant="rect"),
        empty_state=PJXEmptyState(
            id="g-empty",
            title="No results",
            description="Adjust filters or create a new item.",
        ),
        divider_horizontal=PJXDivider(id="g-div-h"),
        divider_labeled=PJXDivider(id="g-div-labeled", label="Or"),
        spinner_small=PJXSpinner(id="g-spin-sm", size="sm"),
        spinner_medium=PJXSpinner(id="g-spin-md", size="md"),
        spinner_large=PJXSpinner(id="g-spin-lg", size="lg"),
        avatar_image=PJXAvatar(
            id="g-av-img",
            src="",
            alt="Sample user",
            initials="IM",
            size="md",
        ),
        avatar_initials=PJXAvatar(id="g-av-in", initials="PJ", size="md"),
        card=PJXCard(
            id="g-card",
            title="Card title",
            body="Card body copy.",
        ),
        breadcrumb=PJXBreadcrumb(
            id="g-crumb",
            items=[("Home", "#"), ("Built-ins", None)],
        ),
        tab_group=PJXTabGroup(
            id="g-tabs",
            tabs={
                "Overview": "<p>First panel content.</p>",
                "Details": "<p>Second panel content.</p>",
            },
        ),
        panel_trigger_alpha=PJXPanelTrigger(
            id="g-panel-tr-a",
            panel_id="g-panel",
            panel="alpha",
            content='<button type="button" class="demo-btn">Alpha</button>',
        ),
        panel_trigger_beta=PJXPanelTrigger(
            id="g-panel-tr-b",
            panel_id="g-panel",
            panel="beta",
            content='<button type="button" class="demo-btn">Beta</button>',
        ),
        panel_host=PJXPanel(
            id="g-panel",
            panels={
                "alpha": "<p>Panel alpha (default). Beta is hidden but still connected to SSE.</p>",
                "beta": (
                    '<div id="g-panel-sse-live" hx-ext="sse" sse-connect="/sse/panel-demo" '
                    'sse-swap="message" style="font-family:monospace;font-size:1.1rem;">waiting…</div>'
                ),
            },
        ),
    )
    return gallery_page.render()


def render_gallery_page() -> str:
    env = Environment(loader=FileSystemLoader(str(_GALLERY_DIR)))
    template = env.get_template("index.html")
    return template.render(gallery_markup=_gallery_inner_html())


def create_app():
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(_GALLERY_DIR)), name="static")

    _SSE_INTERVAL_SEC = 2.5

    @app.get("/", response_class=HTMLResponse)
    def gallery_index() -> str:
        return render_gallery_page()

    @app.get("/sse/panel-demo")
    async def panel_demo_sse() -> StreamingResponse:
        async def event_stream():
            tick_index = 0
            while True:
                tick_index += 1
                yield f"data: SSE tick {tick_index} (~{_SSE_INTERVAL_SEC:g}s apart)\n\n"
                await asyncio.sleep(_SSE_INTERVAL_SEC)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


def run_gallery_server(
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
) -> None:
    import uvicorn

    resolved_port = (
        port
        if port is not None
        else int(os.environ.get("PYJINHX_GALLERY_PORT", str(DEFAULT_GALLERY_PORT)))
    )
    uvicorn.run(
        create_app,
        factory=True,
        host=host,
        port=resolved_port,
    )


if __name__ == "__main__":
    run_gallery_server()
