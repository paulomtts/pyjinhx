"""Kitchen-sink FastAPI app serving real builtins for the browser reactivity tier.

Mirrors the bones of ``tests/integration/app.py`` (full-page shell + rendered
builtins) but wires the production middleware via ``setup()`` so every request
runs inside ``Registry.request_scope``. htmx is loaded from the same jsdelivr
CDN the integration gallery uses.
"""

from __future__ import annotations

import json
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from markupsafe import Markup

from pyjinhx import BaseComponent, PjxSettings, setup
from pyjinhx.builtins import (
    PJXAccordion,
    PJXAccordionContent,
    PJXAccordionGroup,
    PJXAccordionTrigger,
    PJXChipInput,
    PJXDrawer,
    PJXDrawerBody,
    PJXDrawerHeader,
    PJXDropdown,
    PJXLazyLoad,
    PJXModal,
    PJXModalBody,
    PJXModalHeader,
    PJXNotification,
    PJXPageLoader,
    PJXPasswordInput,
    PJXPopover,
    PJXPopoverPanel,
    PJXPopoverTrigger,
    PJXRegionLoader,
    PJXResizableGroup,
    PJXResizableHandle,
    PJXResizablePanel,
    PJXTab,
    PJXTabGroup,
    PJXTabList,
    PJXTabPanel,
    PJXToastHost,
)

_PAGE_TEMPLATE = """
<div class="kitchen-sink-page">
<h1 id="page-title">Reactivity kitchen sink</h1>

<section>
{{ modal }}
<button type="button" id="modal-open-btn" data-pjx-open="rx-modal">Open modal</button>
{{ remove_modal }}
<button type="button" id="remove-modal-open-btn" data-pjx-open="rx-remove-modal">Open remove-on-close modal</button>
</section>

<section>
{{ drawer }}
<button type="button" id="drawer-open-btn" data-pjx-open="rx-drawer">Open drawer</button>
</section>

<section>
{{ popover_a }}
{{ popover_b }}
{{ dropdown }}
</section>

<section>
<form id="chip-form" method="post" action="/chips/echo">
{{ chips }}
<button type="submit" id="chip-submit">Submit</button>
</form>
</section>

<section>
{{ notification }}
<button type="button" id="note-frag-btn"
        hx-get="/fragments/notification" hx-target="body" hx-swap="beforeend">
Fetch notification
</button>
{{ toast_host }}
<button type="button" id="save-btn" hx-post="/actions/save" hx-swap="none">Save</button>
</section>

<section>
<div id="region-wrap" style="position:relative;min-height:80px;">
{{ region_loader }}
<p>Region content</p>
</div>
{{ page_loader }}
<button type="button" id="nav-btn" hx-get="/slow-content" hx-target="#app-content">Navigate</button>
<div id="app-content"><p>Initial content</p></div>
</section>

<section>
{{ panel_trigger_a }}
{{ panel_trigger_b }}
{{ panel }}
</section>

<section>
{{ detached_trigger_0 }}
{{ detached_trigger_1 }}
{{ detached_group }}
</section>

<section>
{{ password }}
{{ tabs }}
</section>

<section>
<div id="rx-resize-box" style="width:400px;height:120px;border:1px solid #ccc;">
{{ resizable }}
</div>
</section>

<section>
<div id="rx-floor-box" style="width:300px;height:200px;border:1px solid #ccc;">
{{ floor_box | safe }}
</div>
</section>

<section>
{{ accordion_box | safe }}
</section>
</div>
"""


class KitchenSinkPage(BaseComponent):
    modal: PJXModal
    remove_modal: PJXModal
    drawer: PJXDrawer
    popover_a: PJXPopover
    popover_b: PJXPopover
    dropdown: PJXDropdown
    chips: PJXChipInput
    notification: PJXNotification
    toast_host: PJXToastHost
    region_loader: PJXRegionLoader
    page_loader: PJXPageLoader
    panel_trigger_a: PJXTab
    panel_trigger_b: PJXTab
    panel: PJXTabGroup
    detached_trigger_0: PJXTab
    detached_trigger_1: PJXTab
    detached_group: PJXTabGroup
    password: PJXPasswordInput
    tabs: PJXTabGroup
    resizable: PJXResizableGroup
    floor_box: str
    accordion_box: str

    def render(self) -> Markup:
        return self._render(source=_PAGE_TEMPLATE.strip())


def _popover(prefix: str, label: str) -> PJXPopover:
    return PJXPopover(
        id=prefix,
        content=(
            str(PJXPopoverTrigger(id=f"{prefix}-t", content=label).render())
            + str(PJXPopoverPanel(id=f"{prefix}-p", content=f"{label} panel content").render())
        ),
    )


def render_page() -> str:
    page = KitchenSinkPage(
        id="kitchen-sink",
        modal=PJXModal(
            id="rx-modal",
            content=(
                str(PJXModalHeader(id="rx-modal-h", title="Demo modal").render())
                + str(PJXModalBody(id="rx-modal-b", content="Modal body.").render())
            ),
        ),
        remove_modal=PJXModal(
            id="rx-remove-modal",
            remove_on_close=True,
            content=str(PJXModalBody(
                id="rx-remove-modal-b",
                content=(
                    '<form id="rx-remove-form" hx-post="/actions/slow-save" hx-swap="none">'
                    '<button type="submit" id="rx-remove-submit" data-pjx-close>Send</button>'
                    "</form>"
                ),
            ).render()),
        ),
        drawer=PJXDrawer(
            id="rx-drawer",
            side="right",
            content=(
                str(PJXDrawerHeader(id="rx-drawer-h", title="Demo drawer").render())
                + str(PJXDrawerBody(id="rx-drawer-b", content="Drawer body.").render())
            ),
        ),
        popover_a=_popover("rx-pop-a", "Open A"),
        popover_b=_popover("rx-pop-b", "Open B"),
        dropdown=PJXDropdown(
            id="rx-drop",
            trigger="Options",
            items=[
                '<button type="button" role="menuitem" id="drop-close-item" data-pjx-close>Close menu</button>',
                '<a role="menuitem" href="#">Plain item</a>',
            ],
        ),
        chips=PJXChipInput(id="rx-chips", name="tags", placeholder="Add tag…"),
        notification=PJXNotification(
            id="rx-note",
            content="Manual note",
            corner="top-right",
            timeout=0,
            autoshow=False,
        ),
        toast_host=PJXToastHost(id="rx-toasts", position="bottom-right", timeout=0),
        region_loader=PJXRegionLoader(id="rx-region"),
        page_loader=PJXPageLoader(id="rx-page-loader", nav_targets="app-content", active_on_load=False),
        panel_trigger_a=PJXTab(
            id="rx-trig-a", panel="rx-panel-panel-a", selected=True,
            content='<span id="trig-a-btn">Panel A</span>',
        ),
        panel_trigger_b=PJXTab(
            id="rx-trig-b", panel="rx-panel-panel-b",
            content='<span id="trig-b-btn">Panel B</span>',
        ),
        panel=PJXTabGroup(
            id="rx-panel",
            content=(
                str(PJXTabPanel(id="rx-panel-panel-a", content="<p>Panel A body</p>").render())
                + str(PJXTabPanel(
                    id="rx-panel-panel-b",
                    content=str(PJXLazyLoad(
                        id="rx-lazy",
                        when="reveal",
                        url="/fragments/lazy",
                        content='<p id="lazy-placeholder">Loading…</p>',
                    ).render()),
                ).render())
            ),
        ),
        detached_trigger_0=PJXTab(
            id="rx-detached-trigger-0", panel="rx-detached-p0", selected=True,
            content='<span id="rx-detached-btn-0">Show 0</span>',
        ),
        detached_trigger_1=PJXTab(
            id="rx-detached-trigger-1", panel="rx-detached-p1",
            content='<span id="rx-detached-btn-1">Show 1</span>',
        ),
        detached_group=PJXTabGroup(
            id="rx-detached-group",
            content=(
                str(PJXTabPanel(id="rx-detached-p0", content="<p>Detached body 0</p>").render())
                + str(PJXTabPanel(id="rx-detached-p1", content="<p>Detached body 1</p>").render())
            ),
        ),
        password=PJXPasswordInput(id="rx-pw"),
        tabs=PJXTabGroup(
            id="rx-tabs",
            content=(
                str(PJXTabList(content=(
                    str(PJXTab(id="rx-tab-one", panel="rx-tabp-one", selected=True, content="One").render())
                    + str(PJXTab(id="rx-tab-two", panel="rx-tabp-two", closeable=True, content="Two").render())
                )).render())
                + str(PJXTabPanel(id="rx-tabp-one", tab="rx-tab-one", content="<p>Tab one body</p>").render())
                + str(PJXTabPanel(id="rx-tabp-two", tab="rx-tab-two", content="<p>Tab two body</p>").render())
            ),
        ),
        resizable=PJXResizableGroup(
            id="rx-resize-group",
            direction="row",
            content=(
                str(PJXResizablePanel(id="rx-resize-left", size=50, min=20, content="<div>left</div>").render())
                + str(PJXResizableHandle(id="rx-resize-handle").render())
                + str(PJXResizablePanel(id="rx-resize-right", size=50, content="<div>right</div>").render())
            ),
        ),
        floor_box=str(PJXResizableGroup(id="rx-floor-group", direction="column", content=(
            str(PJXResizablePanel(id="rx-floor-top", size=60, content="<div>top</div>").render())
            + str(PJXResizableHandle(id="rx-floor-handle").render())
            + str(PJXResizablePanel(id="rx-floor-bottom", size=40, min="content", content='<div id="rx-floor-strip" style="height:36px;flex-shrink:0">strip</div><div>body</div>').render())
        )).render()),
        accordion_box=str(PJXAccordionGroup(id="rx-accordion-group", content=(
            str(PJXAccordion(id="rx-accordion-open", open=False, content=(
                str(PJXAccordionTrigger(id="rx-accordion-trigger-open", content="Open item").render())
                + str(PJXAccordionContent(content="Open item body").render())
            )).render())
            + str(PJXAccordion(id="rx-accordion-disabled", open=False, content=(
                str(PJXAccordionTrigger(id="rx-accordion-trigger-disabled", disabled=True, content="Disabled item").render())
                + str(PJXAccordionContent(content="Disabled item body").render())
            )).render())
        )).render()),
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>pyjinhx reactivity kitchen sink</title>
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"
        integrity="sha384-/TgkGk7p307TH7EXJDuUlgG3Ce1UVolAOFopFekQkkXihi5u/6OCvVKyz1W+idaz"
        crossorigin="anonymous"></script>
</head>
<body>
{page.render()}
</body>
</html>"""


def create_app() -> FastAPI:
    app = FastAPI()
    setup(app, settings=PjxSettings())

    @app.get("/healthz")
    def healthz() -> str:
        return "ok"

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return render_page()

    @app.post("/chips/echo")
    async def chips_echo(request: Request) -> JSONResponse:
        form = await request.form()
        return JSONResponse({"tags": form.getlist("tags")})

    @app.get("/fragments/notification", response_class=HTMLResponse)
    def notification_fragment() -> str:
        return str(
            PJXNotification(
                id="rx-note-frag",
                content="Fragment note",
                corner="bottom-left",
                timeout=600,
                autoshow=True,
            ).render()
        )

    @app.post("/actions/save")
    def save() -> Response:
        headers = {"HX-Trigger": json.dumps({"pjx:toast": {"message": "Saved!", "level": "success"}})}
        return Response(status_code=200, headers=headers)

    @app.post("/actions/slow-save")
    def slow_save() -> Response:
        # Slower than the modal-close animation/fallback (~250ms), so the
        # response lands after a remove_on_close dialog would have removed
        # itself — the race the deferred-removal fix covers.
        time.sleep(0.6)
        headers = {"HX-Trigger": json.dumps({"pjx:toast": {"message": "Slow saved!", "level": "success"}})}
        return Response(status_code=200, headers=headers)

    @app.get("/slow-content", response_class=HTMLResponse)
    def slow_content() -> str:
        time.sleep(0.3)
        return '<p id="slow-loaded">Fresh content</p>'

    @app.get("/fragments/lazy", response_class=HTMLResponse)
    def lazy_fragment() -> str:
        time.sleep(0.2)
        return '<p id="rx-lazy-loaded">Lazy content arrived</p>'

    return app
