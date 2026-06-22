from pyjinhx.builtins import (
    PJXDropdown,
    PJXPageLoader,
    PJXPanel,
    PJXPanelTrigger,
    PJXRegionLoader,
    PJXTab,
    PJXTabGroup,
    PJXTabList,
    PJXTabPanel,
    PJXToastHost,
)


def dropdown():
    return PJXDropdown(
        trigger="Actions",
        items=[
            "<button>Edit</button>",
            "<button>Duplicate</button>",
            "<button>Delete</button>",
        ],
        menu_label="Actions menu",
    ).render()


def tab_group():
    return PJXTabGroup(
        content=(
            PJXTabList(content=(
                PJXTab(id="tg-t0", panel="tg-p0", selected=True, content="Overview").render()
                + PJXTab(id="tg-t1", panel="tg-p1", content="Activity").render()
                + PJXTab(id="tg-t2", panel="tg-p2", closeable=True, content="Settings").render()
            )).render()
            + PJXTabPanel(id="tg-p0", tab="tg-t0", content="<p>Project summary and key metrics.</p>").render()
            + PJXTabPanel(id="tg-p1", tab="tg-t1", content="<p>Recent commits and deploys.</p>").render()
            + PJXTabPanel(id="tg-p2", tab="tg-t2", content="<p>Repository configuration.</p>").render()
        ),
    ).render()


def panel():
    return [
        '<div style="display:flex;gap:0.5rem;margin-bottom:1rem">',
        PJXPanelTrigger(
            panel_id="demo-panel",
            panel="chat",
            content='<button class="pjx-demo-btn">Chat</button>',
        ).render(),
        PJXPanelTrigger(
            panel_id="demo-panel",
            panel="files",
            content='<button class="pjx-demo-btn">Files</button>',
        ).render(),
        PJXPanelTrigger(
            panel_id="demo-panel",
            panel="settings",
            content='<button class="pjx-demo-btn">Settings</button>',
        ).render(),
        "</div>",
        PJXPanel(
            id="demo-panel",
            panels={
                "chat": "<p>Active conversations with your team.</p>",
                "files": "<p>Uploaded assets and project documents.</p>",
                "settings": "<p>Notification preferences and integrations.</p>",
            },
        ).render(),
    ]


def toast_host():
    return [
        '<button class="pjx-demo-btn" onclick="pjx.toast(\'Saved.\')">Show toast</button>',
        PJXToastHost(position="bottom-right").render(),
    ]


def region_loader():
    return [
        '<div style="position:relative;min-height:6rem;padding:1rem;border:1px solid #8884;border-radius:6px">',
        '<p style="margin:0">Region content — click to trigger a loading veil.</p>',
        PJXRegionLoader(id="demo-region").render(),
        "</div>",
        """<button class="pjx-demo-btn" style="margin-top:0.75rem"
            onclick="pjx.loader.region.show('demo-region');setTimeout(()=>pjx.loader.region.hide('demo-region'),1500)">
            Simulate load</button>""",
    ]


def page_loader():
    return [
        PJXPageLoader(id="demo-page-loader").render(),
        """<button class="pjx-demo-btn" style="margin-top:0.75rem"
            onclick="pjx.loader.page.show();setTimeout(()=>pjx.loader.page.hide(),1500)">
            Simulate load</button>""",
    ]


DEMOS = {
    "PJXDropdown": (dropdown, 200),
    "PJXTabGroup": (tab_group, 320),
    "PJXPanel": (panel, 300),
    "PJXToastHost": (toast_host, 160),
    "PJXRegionLoader": (region_loader, 220),
    "PJXPageLoader": (page_loader, 160),
}
