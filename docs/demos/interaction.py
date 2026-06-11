from pyjinhx.builtins import (
    Dropdown,
    PageLoader,
    Panel,
    PanelTrigger,
    RegionLoader,
    TabGroup,
    ToastHost,
)


def dropdown():
    return Dropdown(
        trigger="Actions",
        items=[
            "<button>Edit</button>",
            "<button>Duplicate</button>",
            "<button>Delete</button>",
        ],
        menu_label="Actions menu",
    ).render()


def tab_group():
    return TabGroup(
        tabs={
            "Overview": "<p>Project summary and key metrics.</p>",
            "Activity": "<p>Recent commits and deploys.</p>",
            "Settings": "<p>Repository configuration.</p>",
        },
        tabs_label="Project tabs",
    ).render()


def panel():
    return [
        '<div style="display:flex;gap:0.5rem;margin-bottom:1rem">',
        PanelTrigger(
            panel_id="demo-panel",
            panel="chat",
            content='<button class="px-demo-btn">Chat</button>',
        ).render(),
        PanelTrigger(
            panel_id="demo-panel",
            panel="files",
            content='<button class="px-demo-btn">Files</button>',
        ).render(),
        PanelTrigger(
            panel_id="demo-panel",
            panel="settings",
            content='<button class="px-demo-btn">Settings</button>',
        ).render(),
        "</div>",
        Panel(
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
        '<button class="px-demo-btn" onclick="px.toast(\'Saved.\')">Show toast</button>',
        ToastHost(position="bottom-right").render(),
    ]


def region_loader():
    return [
        '<div style="position:relative;min-height:6rem;padding:1rem;border:1px solid #8884;border-radius:6px">',
        '<p style="margin:0">Region content — click to trigger a loading veil.</p>',
        RegionLoader(id="demo-region").render(),
        "</div>",
        """<button class="px-demo-btn" style="margin-top:0.75rem"
            onclick="px.loader.region.show('demo-region');setTimeout(()=>px.loader.region.hide('demo-region'),1500)">
            Simulate load</button>""",
    ]


def page_loader():
    return [
        PageLoader(id="demo-page-loader").render(),
        """<button class="px-demo-btn" style="margin-top:0.75rem"
            onclick="px.loader.page.show();setTimeout(()=>px.loader.page.hide(),1500)">
            Simulate load</button>""",
    ]


DEMOS = {
    "Dropdown": (dropdown, 200),
    "TabGroup": (tab_group, 320),
    "Panel": (panel, 300),
    "ToastHost": (toast_host, 160),
    "RegionLoader": (region_loader, 220),
    "PageLoader": (page_loader, 160),
}
