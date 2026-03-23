from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import pyjinhx.builtins  # noqa: F401 — register all builtin classes
from pyjinhx import BaseComponent, Renderer
from pyjinhx.builtins import (
    Alert,
    Avatar,
    Badge,
    Breadcrumb,
    Card,
    Divider,
    Dropdown,
    Drawer,
    EmptyState,
    LoadingOverlay,
    Modal,
    Notification,
    Popover,
    Progress,
    Region,
    RegionTrigger,
    Skeleton,
    Spinner,
    TabGroup,
    Tooltip,
)

DEFAULT_GALLERY_PORT = 9000

_GALLERY_DIR = Path(__file__).resolve().parent

_SHOWCASE_TEMPLATE = """
<h2>Badge</h2>
<section class="demo-row">
{{ badge }}
</section>

<h2>Modal</h2>
<section class="demo-stack">
{{ modal }}
<button type="button" class="demo-btn" onclick="openModal('g-modal')">Open modal</button>
</section>

<h2>Notification</h2>
<section class="demo-stack">
{{ notification }}
<button type="button" class="demo-btn" onclick="showNotification('g-toast')">Show notification</button>
</section>

<h2>Popover</h2>
<section class="demo-row">
{{ popover }}
</section>

<h2>Loading overlay</h2>
<section>
<div style="position:relative;min-height:100px;padding:1rem;border:1px dashed var(--border);border-radius:var(--radius-md);">
{{ loading_overlay }}
<p style="margin:0;color:var(--text-muted);font-size:var(--font-size-sm);">Parent is position: relative</p>
</div>
<div class="demo-row" style="margin-top:0.75rem;">
<button type="button" class="demo-btn" onclick="showLoadingOverlay('g-overlay')">Show overlay</button>
<button type="button" class="demo-btn" onclick="hideLoadingOverlay('g-overlay')">Hide overlay</button>
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
<button type="button" class="demo-btn" onclick="openPxDrawer('g-drawer')">Open drawer</button>
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

<h2>Region (distributed triggers)</h2>
<section class="demo-stack">
<p style="margin:0;font-size:var(--font-size-sm);color:var(--text-muted);">Triggers are separate from the panel host.</p>
<div class="demo-row">
{{ region_trigger_alpha }}
{{ region_trigger_beta }}
</div>
{{ region }}
</section>
"""


class BuiltinsGalleryPage(BaseComponent):
    badge: Badge
    modal: Modal
    notification: Notification
    popover: Popover
    loading_overlay: LoadingOverlay
    tooltip: Tooltip
    alert: Alert
    dropdown: Dropdown
    drawer: Drawer
    progress_determinate: Progress
    progress_indeterminate: Progress
    skeleton_text: Skeleton
    skeleton_circle: Skeleton
    skeleton_rect: Skeleton
    empty_state: EmptyState
    divider_horizontal: Divider
    divider_labeled: Divider
    spinner_small: Spinner
    spinner_medium: Spinner
    spinner_large: Spinner
    avatar_image: Avatar
    avatar_initials: Avatar
    card: Card
    breadcrumb: Breadcrumb
    tab_group: TabGroup
    region_trigger_alpha: RegionTrigger
    region_trigger_beta: RegionTrigger
    region: Region

    def render(self) -> str:
        return str(self._render(source=_SHOWCASE_TEMPLATE.strip()))


@lru_cache(maxsize=1)
def _gallery_inner_html() -> str:
    tmp = tempfile.mkdtemp(prefix="pyjinhx-gallery-")
    Renderer.set_default_environment(tmp)
    Renderer.get_default_renderer(auto_id=False)
    gallery_page = BuiltinsGalleryPage(
        id="builtins-gallery",
        badge=Badge(id="g-badge", label="Beta", color="brand", shape="md"),
        modal=Modal(
            id="g-modal",
            title="Demo modal",
            body="Modal body content from the gallery.",
        ),
        notification=Notification(
            id="g-toast",
            content="Toast message",
            corner="top-right",
            timeout=0,
        ),
        popover=Popover(
            id="g-pop",
            content="Hover me",
            card_content="Popover details appear on hover.",
            position="anchor",
            backdrop=True,
        ),
        loading_overlay=LoadingOverlay(id="g-overlay"),
        tooltip=Tooltip(
            id="g-tip",
            trigger="Focus or hover",
            tip="Tooltip copy",
            placement="top",
        ),
        alert=Alert(
            id="g-alert",
            variant="info",
            title="Heads up",
            body="This is an inline alert.",
        ),
        dropdown=Dropdown(
            id="g-drop",
            trigger="Options",
            menu='<a href="#">First</a><a href="#">Second</a>',
        ),
        drawer=Drawer(
            id="g-drawer",
            side="right",
            title="Drawer",
            body="Side panel content.",
        ),
        progress_determinate=Progress(
            id="g-prog-det",
            value=62,
            max=100,
            label="Determinate",
        ),
        progress_indeterminate=Progress(
            id="g-prog-ind",
            max=100,
            label="Indeterminate",
        ),
        skeleton_text=Skeleton(id="g-skel-text", variant="text", lines=3),
        skeleton_circle=Skeleton(id="g-skel-circle", variant="circle"),
        skeleton_rect=Skeleton(id="g-skel-rect", variant="rect"),
        empty_state=EmptyState(
            id="g-empty",
            title="No results",
            description="Adjust filters or create a new item.",
        ),
        divider_horizontal=Divider(id="g-div-h"),
        divider_labeled=Divider(id="g-div-labeled", label="Or"),
        spinner_small=Spinner(id="g-spin-sm", size="sm"),
        spinner_medium=Spinner(id="g-spin-md", size="md"),
        spinner_large=Spinner(id="g-spin-lg", size="lg"),
        avatar_image=Avatar(
            id="g-av-img",
            src="",
            alt="Sample user",
            initials="IM",
            size="md",
        ),
        avatar_initials=Avatar(id="g-av-in", initials="PJ", size="md"),
        card=Card(
            id="g-card",
            title="Card title",
            body="Card body copy.",
        ),
        breadcrumb=Breadcrumb(
            id="g-crumb",
            items=[("Home", "#"), ("Built-ins", None)],
        ),
        tab_group=TabGroup(
            id="g-tabs",
            tabs={
                "Overview": "<p>First panel content.</p>",
                "Details": "<p>Second panel content.</p>",
            },
        ),
        region_trigger_alpha=RegionTrigger(
            id="g-reg-tr-a",
            region_id="g-region",
            panel="alpha",
            label="Alpha",
        ),
        region_trigger_beta=RegionTrigger(
            id="g-reg-tr-b",
            region_id="g-region",
            panel="beta",
            label="Beta",
        ),
        region=Region(
            id="g-region",
            panels={
                "alpha": "<p>Panel alpha</p>",
                "beta": "<p>Panel beta</p>",
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
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(_GALLERY_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def gallery_index() -> str:
        return render_gallery_page()

    return app


def run_gallery_server(
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
) -> None:
    import uvicorn

    resolved_port = port if port is not None else int(
        os.environ.get("PYJINHX_GALLERY_PORT", str(DEFAULT_GALLERY_PORT))
    )
    uvicorn.run(
        "tests.builtins_gallery.app:create_app",
        factory=True,
        host=host,
        port=resolved_port,
    )


if __name__ == "__main__":
    run_gallery_server()
