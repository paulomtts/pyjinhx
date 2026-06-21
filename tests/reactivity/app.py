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
    PJXChipInput,
    PJXDrawer,
    PJXDropdown,
    PJXLazyPanel,
    PJXModal,
    PJXModalBody,
    PJXModalHeader,
    PJXNotification,
    PJXPageLoader,
    PJXPanel,
    PJXPanelTrigger,
    PJXPasswordInput,
    PJXPopover,
    PJXPopoverPanel,
    PJXPopoverTrigger,
    PJXRegionLoader,
    PJXTabGroup,
    PJXToastHost,
)

_PAGE_TEMPLATE = """
<div class="kitchen-sink-page">
<h1 id="page-title">Reactivity kitchen sink</h1>

<section>
{{ modal }}
<button type="button" id="modal-open-btn" data-pjx-open="rx-modal">Open modal</button>
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
{{ password }}
{{ tabs }}
</section>
</div>
"""


class KitchenSinkPage(BaseComponent):
    modal: PJXModal
    drawer: PJXDrawer
    popover_a: PJXPopover
    popover_b: PJXPopover
    dropdown: PJXDropdown
    chips: PJXChipInput
    notification: PJXNotification
    toast_host: PJXToastHost
    region_loader: PJXRegionLoader
    page_loader: PJXPageLoader
    panel_trigger_a: PJXPanelTrigger
    panel_trigger_b: PJXPanelTrigger
    panel: PJXPanel
    password: PJXPasswordInput
    tabs: PJXTabGroup

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
        drawer=PJXDrawer(id="rx-drawer", side="right", title="Demo drawer", body="Drawer body."),
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
        panel_trigger_a=PJXPanelTrigger(
            id="rx-trig-a",
            panel_id="rx-panel",
            panel="a",
            content='<button type="button" id="trig-a-btn">Panel A</button>',
        ),
        panel_trigger_b=PJXPanelTrigger(
            id="rx-trig-b",
            panel_id="rx-panel",
            panel="b",
            content='<button type="button" id="trig-b-btn">Panel B</button>',
        ),
        panel=PJXPanel(
            id="rx-panel",
            panels={
                "a": "<p>Panel A body</p>",
                "b": str(
                    PJXLazyPanel(
                        id="rx-lazy",
                        url="/fragments/lazy",
                        when="reveal",
                        content='<p id="lazy-placeholder">Loading…</p>',
                    ).render()
                ),
            },
        ),
        password=PJXPasswordInput(id="rx-pw"),
        tabs=PJXTabGroup(
            id="rx-tabs",
            tabs={"One": "<p>Tab one body</p>", "Two": "<p>Tab two body</p>"},
        ),
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

    @app.get("/slow-content", response_class=HTMLResponse)
    def slow_content() -> str:
        time.sleep(0.3)
        return '<p id="slow-loaded">Fresh content</p>'

    @app.get("/fragments/lazy", response_class=HTMLResponse)
    def lazy_fragment() -> str:
        time.sleep(0.2)
        return '<p id="rx-lazy-loaded">Lazy content arrived</p>'

    return app
