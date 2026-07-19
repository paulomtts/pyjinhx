from pyjinhx.builtins import (
    PJXCarousel,
    PJXCarouselSlide,
    PJXDropdown,
    PJXPageLoader,
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
    group = PJXTabGroup(
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
    # A PJXTab used OUTSIDE a PJXTabList becomes a standalone "panel mode"
    # trigger: it drives the group's panels from anywhere (resolved via the
    # panel its `panel=` points at). Wrap inert content — the PJXTab is itself
    # the control.
    standalone = PJXTab(
        panel="tg-p2", content='<span class="pjx-demo-btn">Jump to Settings &darr;</span>'
    ).render()
    # The group fills its container (width:100%); the centering demo page would
    # otherwise shrink-wrap it, so give it a definite width to render against.
    return (
        '<div style="width: 340px; max-width: 100%;">'
        f"{group}"
        '<p style="margin:0.75rem 0 0.35rem;font-size:0.8rem;opacity:0.7">'
        "Standalone trigger (outside the tab list):</p>"
        f"{standalone}"
        "</div>"
    )


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


def carousel():
    def slide(color: str, text: str) -> str:
        return (
            f'<div style="display:flex;align-items:center;justify-content:center;'
            f'height:200px;background:{color};color:#fff;font-size:1.1rem;'
            f'font-weight:600">{text}</div>'
        )

    return PJXCarousel(
        label="Demo photos",
        content=(
            PJXCarouselSlide(label="Slide one", content=slide("#6366f1", "Slide 1")).render()
            + PJXCarouselSlide(label="Slide two", content=slide("#0ea5e9", "Slide 2")).render()
            + PJXCarouselSlide(label="Slide three", content=slide("#22c55e", "Slide 3")).render()
        ),
    ).render()


DEMOS = {
    "PJXDropdown": (dropdown, 320),
    "PJXTabGroup": (tab_group, 440),
    "PJXToastHost": (toast_host, 160),
    "PJXRegionLoader": (region_loader, 220),
    "PJXPageLoader": (page_loader, 160),
    "PJXCarousel": (carousel, 320),
}
