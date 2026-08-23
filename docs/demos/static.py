from pyjinhx.builtins.pjx_paginator import PJXPaginator
from pyjinhx.builtins.pjx_table import PJXTable
from pyjinhx.builtins.pjx_table_body import PJXTableBody
from pyjinhx.builtins.pjx_table_cell import PJXTableCell
from pyjinhx.builtins.pjx_table_head import PJXTableHead
from pyjinhx.builtins.pjx_table_header_cell import PJXTableHeaderCell
from pyjinhx.builtins.pjx_table_row import PJXTableRow
from pyjinhx.builtins.ui.pjx_accordion import PJXAccordion
from pyjinhx.builtins.ui.pjx_accordion_content import PJXAccordionContent
from pyjinhx.builtins.ui.pjx_accordion_group import PJXAccordionGroup
from pyjinhx.builtins.ui.pjx_accordion_trigger import PJXAccordionTrigger
from pyjinhx.builtins.ui.pjx_avatar import PJXAvatar
from pyjinhx.builtins.ui.pjx_avatar_stack import PJXAvatarStack
from pyjinhx.builtins.ui.pjx_badge import PJXBadge
from pyjinhx.builtins.ui.pjx_breadcrumb import PJXBreadcrumb
from pyjinhx.builtins.ui.pjx_button import PJXButton
from pyjinhx.builtins.ui.pjx_card import PJXCard
from pyjinhx.builtins.ui.pjx_card_body import PJXCardBody
from pyjinhx.builtins.ui.pjx_card_footer import PJXCardFooter
from pyjinhx.builtins.ui.pjx_card_header import PJXCardHeader
from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.builtins.ui.pjx_empty_state import PJXEmptyState
from pyjinhx.builtins.ui.pjx_icon import PJXIcon
from pyjinhx.builtins.ui.pjx_progress import PJXProgress
from pyjinhx.builtins.ui.pjx_resizable_group import PJXResizableGroup
from pyjinhx.builtins.ui.pjx_resizable_handle import PJXResizableHandle
from pyjinhx.builtins.ui.pjx_resizable_panel import PJXResizablePanel
from pyjinhx.builtins.ui.pjx_skeleton import PJXSkeleton
from pyjinhx.builtins.ui.pjx_spinner import PJXSpinner


def accordion():
    return PJXAccordion(
        content=PJXAccordionTrigger(content="What is pyjinhx?").render()
        + PJXAccordionContent(
            content="<p>A Python/Jinja HTML component framework.</p>"
        ).render(),
    ).render()


def accordion_group():
    def item(title, body, **kw):
        return PJXAccordion(
            content=PJXAccordionTrigger(content=title).render()
            + PJXAccordionContent(content=body).render(),
            **kw,
        ).render()

    return PJXAccordionGroup(
        mode="exclusive",
        gap="0.25rem",
        content=item("Section A", "<p>Content A.</p>")
        + item("Section B", "<p>Content B.</p>", open=False)
        + item("Section C", "<p>Content C.</p>", open=False),
    ).render()


def badge():
    return [
        PJXBadge(label="Active", color="brand").render(),
        PJXBadge(label="Error", color="error").render(),
        PJXBadge(label="Neutral", color="neutral").render(),
        PJXBadge(label="Beta", color="muted", shape="full").render(),
    ]


def card():
    return PJXCard(
        content=PJXCardHeader(title="Quarterly report").render()
        + PJXCardBody(content="Revenue grew 12% over Q1.").render()
        + PJXCardFooter(content="Updated today").render(),
    ).render()


def divider():
    return PJXDivider(orientation="horizontal", label="or continue with").render()


def spinner():
    return [
        PJXSpinner(size="sm", label="Loading data").render(),
        PJXSpinner(size="md", label="Loading data").render(),
        PJXSpinner(size="lg", label="Loading data").render(),
    ]


def avatar():
    return [
        PJXAvatar(initials="JD", size="sm", alt="Jane Doe").render(),
        PJXAvatar(initials="JD", size="md", alt="Jane Doe").render(),
        PJXAvatar(initials="JD", size="lg", alt="Jane Doe").render(),
        PJXAvatar(initials="JD", size=64, alt="Jane Doe").render(),
    ]


def avatar_shapes():
    return [
        PJXAvatar(initials="JD", size="lg", shape="circle", alt="Circle").render(),
        PJXAvatar(initials="JD", size="lg", shape="square", alt="Square").render(),
        PJXAvatar(initials="JD", size="lg", shape="hexagon", alt="Hexagon").render(),
        PJXAvatar(initials="JD", size="lg", shape="diamond", alt="Diamond").render(),
        PJXAvatar(initials="JD", size="lg", shape="triangle", alt="Triangle").render(),
    ]


def avatar_stack():
    return PJXAvatarStack(
        avatars=[
            PJXAvatar(initials="AB", size="sm", alt="Alice Brown"),
            PJXAvatar(initials="CD", size="sm", alt="Carol Davis"),
            PJXAvatar(initials="EF", size="sm", alt="Eve Foster"),
        ],
        extra_count=4,
    ).render()


def breadcrumb():
    return PJXBreadcrumb(
        items=[("Home", "/"), ("Projects", "/projects"), ("Dashboard", None)]
    ).render()


def skeleton():
    # A horizontal "avatar + lines" loading row — compact, fits a short box.
    # Build via f-string over str()-wrapped renders: concatenating a plain str
    # with a Markup via `+` would trigger Markup.__radd__ and escape the str.
    circle = str(PJXSkeleton(variant="circle").render())
    lines = str(PJXSkeleton(variant="text", lines=2).render())
    # The circle's own .pjx-skeleton is width:100%, so cap it in a fixed box;
    # the lines take the remaining space.
    return (
        '<div style="display:flex;align-items:center;gap:0.85rem;width:280px;max-width:100%">'
        f'<div style="width:2.5rem;flex:none">{circle}</div>'
        f'<div style="flex:1;min-width:0">{lines}</div></div>'
    )


def progress():
    return [
        PJXProgress(value=65, max=100, label="Upload progress").render(),
        PJXProgress(label="Processing").render(),
    ]


def empty_state():
    return PJXEmptyState(
        content='<h3>No results</h3><p>Try a different search term.</p><button class="pjx-demo-btn">Clear filters</button>',
        suggestions=[
            {"label": "Draft a message"},
            {"label": "Summarise a thread"},
        ],
    ).render()


def icon():
    return [
        PJXIcon(name="plus", size=24, label="Add").render(),
        PJXIcon(name="search", size=24, label="Search").render(),
        PJXIcon(name="trash", size=24, label="Delete").render(),
        PJXIcon(name="settings", size=24, label="Settings").render(),
        PJXIcon(name="chevron-right", size=24, label="Next").render(),
    ]


def button():
    return [
        PJXButton(content="Save", variant="primary").render(),
        PJXButton(content="Cancel").render(),
        PJXButton(content="Saving", variant="primary", loading=True).render(),
        PJXButton(content="Disabled", disabled=True).render(),
    ]


def resizable_group():
    return PJXResizableGroup(
        direction="row",
        content=(
            PJXResizablePanel(
                size=40, min=20, content="<div style='padding:0.75rem'>Left</div>"
            ).render()
            + PJXResizableHandle().render()
            + PJXResizablePanel(
                size=60,
                content="<div style='padding:0.75rem'>Right (drag the divider)</div>",
            ).render()
        ),
    ).render()


def paginator():
    return PJXPaginator(page=4, total_pages=12, url="/items?page={page}").render()


def table():
    return PJXTable(
        caption="Team members",
        striped=True,
        bordered="horizontal",
        content=(
            PJXTableHead(
                content=PJXTableRow(
                    content=(
                        # Leading header cell aligns the column with the body rows'
                        # auto-prepended selection checkbox (see the select-all rule).
                        PJXTableHeaderCell(content="").render()
                        + PJXTableHeaderCell(
                            sortable=True, sort="asc", content="Name"
                        ).render()
                        + PJXTableHeaderCell(content="Role").render()
                    )
                ).render()
            ).render()
            + PJXTableBody(
                content=(
                    PJXTableRow(
                        selectable=True,
                        value="1",
                        content=(
                            PJXTableCell(content="Ada Lovelace").render()
                            + PJXTableCell(content="Engineer").render()
                        ),
                    ).render()
                    + PJXTableRow(
                        selectable=True,
                        value="2",
                        content=(
                            PJXTableCell(content="Alan Turing").render()
                            + PJXTableCell(content="Researcher").render()
                        ),
                    ).render()
                )
            ).render()
        ),
    ).render()


DEMOS = {
    "PJXAccordion": (accordion, 160),
    "PJXAccordionGroup": (accordion_group, 260),
    "PJXBadge": (badge, 140),
    "PJXCard": (card, 220),
    "PJXDivider": (divider, 120),
    "PJXSpinner": (spinner, 140),
    "PJXAvatar": (avatar, 140),
    "PJXAvatarShapes": (avatar_shapes, 140),
    "PJXAvatarStack": (avatar_stack, 120),
    "PJXBreadcrumb": (breadcrumb, 120),
    "PJXSkeleton": (skeleton, 150),
    "PJXProgress": (progress, 170),
    "PJXEmptyState": (empty_state, 340),
    "PJXIcon": (icon, 140),
    "PJXButton": (button, 140),
    "PJXResizableGroup": (resizable_group, 160),
    "PJXTable": (table, 260),
    "PJXPaginator": (paginator, 130),
}
