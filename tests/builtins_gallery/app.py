from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import pyjinhx.builtins  # noqa: F401 — register all builtin classes
from pyjinhx import Renderer

DEFAULT_GALLERY_PORT = 9000

_GALLERY_DIR = Path(__file__).resolve().parent

_SHOWCASE_MARKUP = """
<h2>Badge</h2>
<section class="demo-row">
<Badge id="g-badge" label="Beta" color="brand" shape="md"/>
</section>

<h2>Modal</h2>
<section class="demo-stack">
<Modal id="g-modal" title="Demo modal" body="Modal body content from the gallery."/>
<button type="button" class="demo-btn" onclick="openModal('g-modal')">Open modal</button>
</section>

<h2>Notification</h2>
<section class="demo-stack">
<Notification id="g-toast" corner="top-right" timeout="0">Toast message</Notification>
<button type="button" class="demo-btn" onclick="showNotification('g-toast')">Show notification</button>
</section>

<h2>Popover</h2>
<section class="demo-row">
<Popover id="g-pop" card_content="Popover details appear on hover." position="anchor">Hover me</Popover>
</section>

<h2>Loading overlay</h2>
<section>
<div style="position:relative;min-height:100px;padding:1rem;border:1px dashed var(--border);border-radius:var(--radius-md);">
<LoadingOverlay id="g-overlay"/>
<p style="margin:0;color:var(--text-muted);font-size:var(--font-size-sm);">Parent is position: relative</p>
</div>
<div class="demo-row" style="margin-top:0.75rem;">
<button type="button" class="demo-btn" onclick="showLoadingOverlay('g-overlay')">Show overlay</button>
<button type="button" class="demo-btn" onclick="hideLoadingOverlay('g-overlay')">Hide overlay</button>
</div>
</section>

<h2>Tooltip</h2>
<section class="demo-row">
<Tooltip id="g-tip" trigger="Focus or hover" tip="Tooltip copy" placement="top"/>
</section>

<h2>Alert</h2>
<section class="demo-stack">
<Alert id="g-alert" variant="info" title="Heads up" body="This is an inline alert."/>
</section>

<h2>Dropdown</h2>
<section class="demo-row">
<Dropdown id="g-drop" trigger="Options" menu="&lt;a href=&quot;#&quot;&gt;First&lt;/a&gt;&lt;a href=&quot;#&quot;&gt;Second&lt;/a&gt;"/>
</section>

<h2>Drawer</h2>
<section class="demo-stack">
<Drawer id="g-drawer" side="right" title="Drawer" body="Side panel content."/>
<button type="button" class="demo-btn" onclick="openPxDrawer('g-drawer')">Open drawer</button>
</section>

<h2>Progress</h2>
<section class="demo-stack">
<Progress id="g-prog-det" value="62" max="100" label="Determinate"/>
<Progress id="g-prog-ind" max="100" label="Indeterminate"/>
</section>

<h2>Skeleton</h2>
<section class="demo-stack">
<Skeleton id="g-skel-text" variant="text" lines="3"/>
<div style="max-width:8rem"><Skeleton id="g-skel-circle" variant="circle"/></div>
<Skeleton id="g-skel-rect" variant="rect"/>
</section>

<h2>Empty state</h2>
<section>
<EmptyState id="g-empty" title="No results" description="Adjust filters or create a new item."/>
</section>

<h2>Divider</h2>
<section class="demo-stack">
<Divider id="g-div-h"/>
<p style="margin:0;font-size:var(--font-size-sm);color:var(--text-muted);">Plain horizontal rule</p>
<Divider id="g-div-labeled" label="Or"/>
</section>

<h2>Spinner</h2>
<section class="demo-row">
<Spinner id="g-spin-sm" size="sm"/>
<Spinner id="g-spin-md" size="md"/>
<Spinner id="g-spin-lg" size="lg"/>
</section>

<h2>Avatar</h2>
<section class="demo-row">
<Avatar id="g-av-img" src="" alt="Sample user" initials="IM" size="md"/>
<Avatar id="g-av-in" initials="PJ" size="md"/>
</section>

<h2>Card</h2>
<section class="demo-stack">
<Card id="g-card" title="Card title" body="Card body copy."/>
</section>

<h2>Breadcrumb</h2>
<section>
<Breadcrumb id="g-crumb" items='[["Home","#"],["Built-ins",null]]'/>
</section>

<h2>Tab group</h2>
<section>
<TabGroup id="g-tabs" tabs='{"Overview":"<p>First panel content.</p>","Details":"<p>Second panel content.</p>"}'/>
</section>

<h2>Region (distributed triggers)</h2>
<section class="demo-stack">
<p style="margin:0;font-size:var(--font-size-sm);color:var(--text-muted);">Triggers are separate from the panel host.</p>
<div class="demo-row">
<RegionTrigger id="g-reg-tr-a" region_id="g-region" panel="alpha" label="Alpha"/>
<RegionTrigger id="g-reg-tr-b" region_id="g-region" panel="beta" label="Beta"/>
</div>
<Region id="g-region" panels='{"alpha":"<p>Panel alpha</p>","beta":"<p>Panel beta</p>"}'/>
</section>
"""


@lru_cache(maxsize=1)
def _gallery_inner_html() -> str:
    tmp = tempfile.mkdtemp(prefix="pyjinhx-gallery-")
    Renderer.set_default_environment(tmp)
    renderer = Renderer.get_default_renderer(auto_id=False)
    return renderer.render(_SHOWCASE_MARKUP.strip())


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
