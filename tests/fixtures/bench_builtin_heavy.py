"""Shared "builtin-heavy page" used by scripts/bench_v0_vs_v2.py (issue #537).

One composition covering all five L4 builtin families, expressed twice — once
against pyjinhx v0.36.4, once against pyjinhx2 — so the two renderers are
timed on the same logical page.

Excluded builtins (present in v0.36.4 but not ported to v2, so dropped from
BOTH sides to keep the comparison 1:1 — confirmed via a v0.36.4-tag vs
pyjinhx2/builtins/ui diff, issue #537 Task 0): PJXConfirmDialog,
PJXPromptDialog. v2 also splits PJXPopover into a trigger/panel pair that
v0.36.4 does not have; this fixture uses only the bare, self-closing
PJXPopover root on both sides.

**Why the two sides are built differently (deviation from the plan's original
single-markup-string design):** v0.36 (`pyjinhx.Renderer.render(source: str)`)
expands PascalCase tags recursively at any nesting depth from one markup
string — a flat string works for the whole page. pyjinhx2's tag scanner
(`segments.VerbatimParser`) deliberately cuts only the *outermost* open
component tag per parse and leaves what is nested inside it verbatim "for a
later level's parse to deal with" (see `segments.py`); that later level's
parse only sees the nested tags if the string carrying them survives into the
child's own template unescaped. As verified with a throwaway two-line
repro (`<PJXCard><PJXCardBody>...` one level deep, run outside this fixture
during Task 3's exploration) plain `str`-typed Slot content does *not* survive
Jinja's `autoescape=True` unescaped, so a markup string nested more than one
custom tag deep silently renders as escaped text on the v2 side — a
pre-existing renderer gap, not something #537 is scoped to fix (its
non-goals explicitly rule out changing either renderer to fix a finding).
So: `build_v0_page`/`build_v0_table`/`build_v0_shells` return **markup
strings** (v0's native shape); `build_v2_page`/`build_v2_table`/
`build_v2_shells` return a **component instance tree** built by nesting real
`pyjinhx2.builtins` classes directly in Python — the shape v2's own test
suite (e.g. `test_family_composed_shells_sweep.py`) uses for multi-level
composition, and the one that actually renders every builtin instead of
escaping it into inert text.
"""

from pyjinhx2.builtins.pjx_lazy_load import PJXLazyLoad
from pyjinhx2.builtins.pjx_page_loader import PJXPageLoader
from pyjinhx2.builtins.pjx_paginator import PJXPaginator
from pyjinhx2.builtins.pjx_region_loader import PJXRegionLoader
from pyjinhx2.builtins.pjx_table import PJXTable
from pyjinhx2.builtins.pjx_table_body import PJXTableBody
from pyjinhx2.builtins.pjx_table_cell import PJXTableCell
from pyjinhx2.builtins.pjx_table_head import PJXTableHead
from pyjinhx2.builtins.pjx_table_header_cell import PJXTableHeaderCell
from pyjinhx2.builtins.pjx_table_row import PJXTableRow
from pyjinhx2.builtins.ui.pjx_accordion import PJXAccordion
from pyjinhx2.builtins.ui.pjx_accordion_content import PJXAccordionContent
from pyjinhx2.builtins.ui.pjx_accordion_group import PJXAccordionGroup
from pyjinhx2.builtins.ui.pjx_accordion_trigger import PJXAccordionTrigger
from pyjinhx2.builtins.ui.pjx_alert import PJXAlert
from pyjinhx2.builtins.ui.pjx_avatar import PJXAvatar
from pyjinhx2.builtins.ui.pjx_avatar_stack import PJXAvatarStack
from pyjinhx2.builtins.ui.pjx_badge import PJXBadge
from pyjinhx2.builtins.ui.pjx_breadcrumb import PJXBreadcrumb
from pyjinhx2.builtins.ui.pjx_button import PJXButton
from pyjinhx2.builtins.ui.pjx_card import PJXCard
from pyjinhx2.builtins.ui.pjx_card_body import PJXCardBody
from pyjinhx2.builtins.ui.pjx_card_footer import PJXCardFooter
from pyjinhx2.builtins.ui.pjx_card_header import PJXCardHeader
from pyjinhx2.builtins.ui.pjx_carousel import PJXCarousel
from pyjinhx2.builtins.ui.pjx_carousel_slide import PJXCarouselSlide
from pyjinhx2.builtins.ui.pjx_chip_input import PJXChipInput
from pyjinhx2.builtins.ui.pjx_divider import PJXDivider
from pyjinhx2.builtins.ui.pjx_drawer import PJXDrawer
from pyjinhx2.builtins.ui.pjx_drawer_body import PJXDrawerBody
from pyjinhx2.builtins.ui.pjx_drawer_footer import PJXDrawerFooter
from pyjinhx2.builtins.ui.pjx_drawer_header import PJXDrawerHeader
from pyjinhx2.builtins.ui.pjx_dropdown import PJXDropdown
from pyjinhx2.builtins.ui.pjx_form_field import PJXFormField
from pyjinhx2.builtins.ui.pjx_icon import PJXIcon
from pyjinhx2.builtins.ui.pjx_modal import PJXModal
from pyjinhx2.builtins.ui.pjx_modal_body import PJXModalBody
from pyjinhx2.builtins.ui.pjx_modal_footer import PJXModalFooter
from pyjinhx2.builtins.ui.pjx_modal_header import PJXModalHeader
from pyjinhx2.builtins.ui.pjx_notification import PJXNotification
from pyjinhx2.builtins.ui.pjx_password_input import PJXPasswordInput
from pyjinhx2.builtins.ui.pjx_popover import PJXPopover
from pyjinhx2.builtins.ui.pjx_progress import PJXProgress
from pyjinhx2.builtins.ui.pjx_resizable_group import PJXResizableGroup
from pyjinhx2.builtins.ui.pjx_resizable_handle import PJXResizableHandle
from pyjinhx2.builtins.ui.pjx_resizable_panel import PJXResizablePanel
from pyjinhx2.builtins.ui.pjx_segmented_control import PJXSegmentedControl
from pyjinhx2.builtins.ui.pjx_skeleton import PJXSkeleton
from pyjinhx2.builtins.ui.pjx_spinner import PJXSpinner
from pyjinhx2.builtins.ui.pjx_tab import PJXTab
from pyjinhx2.builtins.ui.pjx_tab_group import PJXTabGroup
from pyjinhx2.builtins.ui.pjx_tab_list import PJXTabList
from pyjinhx2.builtins.ui.pjx_tab_panel import PJXTabPanel
from pyjinhx2.builtins.ui.pjx_toast_host import PJXToastHost
from pyjinhx2.builtins.ui.pjx_toggle_switch import PJXToggleSwitch
from pyjinhx2.builtins.ui.pjx_tooltip import PJXTooltip
from pyjinhx2.builtins.ui.pjx_tooltip_content import PJXTooltipContent
from pyjinhx2.builtins.ui.pjx_tooltip_trigger import PJXTooltipTrigger
from pyjinhx2.component import BaseComponent, Slot

EXCLUDED_FROM_BOTH = (
    "PJXConfirmDialog",
    "PJXPromptDialog",
)

# Logical name -> v0.36 tag string. v2's manifest (V2_MANIFEST, below) holds
# the same names as the class __name__ values actually placed in the v2 tree
# — both lists are the identical set of strings today; the split exists so a
# future rename during the port stays visible in one place.
V0_TAGS: dict[str, str] = {
    "icon": "PJXIcon",
    "badge": "PJXBadge",
    "avatar": "PJXAvatar",
    "avatar_stack": "PJXAvatarStack",
    "divider": "PJXDivider",
    "progress": "PJXProgress",
    "skeleton": "PJXSkeleton",
    "spinner": "PJXSpinner",
    "breadcrumb": "PJXBreadcrumb",
    "button": "PJXButton",
    "form_field": "PJXFormField",
    "password_input": "PJXPasswordInput",
    "chip_input": "PJXChipInput",
    "segmented_control": "PJXSegmentedControl",
    "toggle_switch": "PJXToggleSwitch",
    "card": "PJXCard",
    "card_header": "PJXCardHeader",
    "card_body": "PJXCardBody",
    "card_footer": "PJXCardFooter",
    "modal": "PJXModal",
    "modal_header": "PJXModalHeader",
    "modal_body": "PJXModalBody",
    "modal_footer": "PJXModalFooter",
    "drawer": "PJXDrawer",
    "drawer_header": "PJXDrawerHeader",
    "drawer_body": "PJXDrawerBody",
    "drawer_footer": "PJXDrawerFooter",
    "accordion": "PJXAccordion",
    "accordion_group": "PJXAccordionGroup",
    "accordion_trigger": "PJXAccordionTrigger",
    "accordion_content": "PJXAccordionContent",
    "tab": "PJXTab",
    "tab_group": "PJXTabGroup",
    "tab_list": "PJXTabList",
    "tab_panel": "PJXTabPanel",
    "popover": "PJXPopover",
    "dropdown": "PJXDropdown",
    "tooltip": "PJXTooltip",
    "tooltip_trigger": "PJXTooltipTrigger",
    "tooltip_content": "PJXTooltipContent",
    "table": "PJXTable",
    "table_body": "PJXTableBody",
    "table_head": "PJXTableHead",
    "table_header_cell": "PJXTableHeaderCell",
    "table_row": "PJXTableRow",
    "table_cell": "PJXTableCell",
    "paginator": "PJXPaginator",
    "region_loader": "PJXRegionLoader",
    "page_loader": "PJXPageLoader",
    "lazy_load": "PJXLazyLoad",
    "carousel": "PJXCarousel",
    "carousel_slide": "PJXCarouselSlide",
    "notification": "PJXNotification",
    "toast_host": "PJXToastHost",
    "alert": "PJXAlert",
    "resizable_group": "PJXResizableGroup",
    "resizable_handle": "PJXResizableHandle",
    "resizable_panel": "PJXResizablePanel",
}

V0_MANIFEST = list(V0_TAGS.values())
# Same set of names today (see module docstring for why the v2 side is built
# from real class instances instead of tags parsed out of markup).
V2_MANIFEST = list(V0_TAGS.values())


def component_names(component: BaseComponent) -> set[str]:
    """Every component class name reachable from ``component``'s Slot fields.

    Walks whatever the descriptor marks as slot fields, recursing into nested
    components and the items of list/dict slot values. Used by the parity
    test (and available to the bench script) to confirm the v2 tree actually
    contains the manifest's components, since v2's tree is built in Python
    rather than parsed back out of a markup string.
    """
    names = {type(component).__name__}
    descriptor = component.__pjx_descriptor__
    for field_name in descriptor.slot_fields:
        value = getattr(component, field_name, None)
        for item in value if isinstance(value, (list, tuple)) else (value,):
            if isinstance(item, BaseComponent):
                names |= component_names(item)
    return names


# ---------------------------------------------------------------------------
# v0.36 side: markup strings, v0's native shape.
# ---------------------------------------------------------------------------


def _v0_display_primitives() -> str:
    return (
        '<PJXIcon id="p-icon" name="settings"/>'
        '<PJXBadge id="p-badge" label="new" color="brand"/>'
        '<PJXAvatar id="p-avatar" initials="AB"/>'
        '<PJXAvatarStack id="p-avatar-stack"/>'
        '<PJXDivider id="p-divider"/>'
        '<PJXProgress id="p-progress" value="42"/>'
        '<PJXSkeleton id="p-skeleton"/>'
        '<PJXSpinner id="p-spinner"/>'
        '<PJXBreadcrumb id="p-breadcrumb"/>'
    )


def _v0_form_block() -> str:
    return (
        '<PJXFormField id="f-password"><PJXPasswordInput id="pw-input" name="password"/></PJXFormField>'
        '<PJXFormField id="f-chip"><PJXChipInput id="chip-input" name="tags"/></PJXFormField>'
        '<PJXSegmentedControl id="f-segmented" name="mode"/>'
        '<PJXToggleSwitch id="f-toggle" name="opt-in"/>'
        '<PJXButton id="f-submit" type="submit">Save</PJXButton>'
    )


def _v0_table(rows: int) -> str:
    parts = [
        (
            '<PJXTable id="bench-table">'
            '<PJXTableHead id="bench-thead"><PJXTableRow id="head-row">'
            '<PJXTableHeaderCell id="hc-name">Name</PJXTableHeaderCell>'
            '<PJXTableHeaderCell id="hc-value">Value</PJXTableHeaderCell>'
            '<PJXTableHeaderCell id="hc-score">Score</PJXTableHeaderCell>'
            "</PJXTableRow></PJXTableHead>"
            '<PJXTableBody id="bench-tbody">'
        )
    ]
    for r in range(rows):
        parts.append(
            f'<PJXTableRow id="r{r}">'
            f'<PJXTableCell id="c{r}a">name {r}</PJXTableCell>'
            f'<PJXTableCell id="c{r}b"><input type="text" value="v{r}"/></PJXTableCell>'
            f'<PJXTableCell id="c{r}c">{r * 3}</PJXTableCell>'
            f"</PJXTableRow>"
        )
    parts.append("</PJXTableBody></PJXTable>")
    return "".join(parts)


def _v0_data_nav() -> str:
    return (
        '<PJXPaginator id="bench-paginator" page="2" total_pages="10" url="/bench?page={page}"/>'
        '<PJXRegionLoader id="bench-region-loader"/>'
        '<PJXPageLoader id="bench-page-loader"/>'
        '<PJXLazyLoad id="bench-lazy-load" url="/bench/more"/>'
    )


def _v0_shells(inner: str) -> str:
    """Modal -> Accordion -> TabGroup shell nest, wrapping ``inner``."""
    return (
        '<PJXModal id="bench-modal">'
        '<PJXModalHeader id="bench-modal-header">Details</PJXModalHeader>'
        '<PJXModalBody id="bench-modal-body">'
        '<PJXAccordionGroup id="bench-acc-group">'
        '<PJXAccordion id="bench-acc">'
        '<PJXAccordionTrigger id="bench-acc-trigger">Details</PJXAccordionTrigger>'
        '<PJXAccordionContent id="bench-acc-content">'
        '<PJXTabGroup id="bench-tabs">'
        '<PJXTabList id="bench-tab-list">'
        '<PJXTab id="bench-tab-1" panel="bench-tab-panel-1">Data</PJXTab>'
        "</PJXTabList>"
        f'<PJXTabPanel id="bench-tab-panel-1">{inner}</PJXTabPanel>'
        "</PJXTabGroup>"
        "</PJXAccordionContent>"
        "</PJXAccordion>"
        "</PJXAccordionGroup>"
        "</PJXModalBody>"
        '<PJXModalFooter id="bench-modal-footer">Close</PJXModalFooter>'
        "</PJXModal>"
    )


def _v0_cards_dropdown_popover_tooltip() -> str:
    return (
        '<PJXCard id="bench-card">'
        '<PJXCardHeader id="bench-card-header">Overview</PJXCardHeader>'
        '<PJXCardBody id="bench-card-body">Summary text.</PJXCardBody>'
        '<PJXCardFooter id="bench-card-footer">'
        '<PJXPopover id="bench-popover"/>'
        '<PJXDropdown id="bench-dropdown" trigger="More"/>'
        '<PJXTooltip id="bench-tooltip">'
        '<PJXTooltipTrigger id="bench-tooltip-trigger">?</PJXTooltipTrigger>'
        '<PJXTooltipContent id="bench-tooltip-content">Help text</PJXTooltipContent>'
        "</PJXTooltip>"
        "</PJXCardFooter>"
        "</PJXCard>"
        '<PJXDrawer id="bench-drawer">'
        '<PJXDrawerHeader id="bench-drawer-header">Filters</PJXDrawerHeader>'
        '<PJXDrawerBody id="bench-drawer-body">Body</PJXDrawerBody>'
        '<PJXDrawerFooter id="bench-drawer-footer">Close</PJXDrawerFooter>'
        "</PJXDrawer>"
    )


def _v0_js_heavy_tail() -> str:
    return (
        '<PJXCarousel id="bench-carousel">'
        '<PJXCarouselSlide id="bench-slide-1">One</PJXCarouselSlide>'
        '<PJXCarouselSlide id="bench-slide-2">Two</PJXCarouselSlide>'
        "</PJXCarousel>"
        '<PJXNotification id="bench-notification">Saved</PJXNotification>'
        '<PJXToastHost id="bench-toast-host"/>'
        '<PJXAlert id="bench-alert">Heads up</PJXAlert>'
        '<PJXResizableGroup id="bench-resizable">'
        '<PJXResizablePanel id="bench-resizable-panel-1">Left</PJXResizablePanel>'
        '<PJXResizableHandle id="bench-resizable-handle"/>'
        '<PJXResizablePanel id="bench-resizable-panel-2">Right</PJXResizablePanel>'
        "</PJXResizableGroup>"
    )


def build_v0_page(rows: int) -> str:
    """The full builtin-heavy page (v0.36 markup string)."""
    table_and_data = _v0_table(rows) + _v0_data_nav()
    body = (
        _v0_display_primitives()
        + _v0_form_block()
        + _v0_shells(table_and_data)
        + _v0_cards_dropdown_popover_tooltip()
        + _v0_js_heavy_tail()
    )
    return f'<div id="bench-root">{body}</div>'


def build_v0_table(rows: int) -> str:
    return _v0_table(rows) + _v0_data_nav()


def build_v0_shells() -> str:
    return _v0_shells(_v0_cards_dropdown_popover_tooltip())


# ---------------------------------------------------------------------------
# v2 side: real component instances nested in Python (see module docstring).
# ---------------------------------------------------------------------------


class BenchPage(BaseComponent):
    """Root wrapper for the v2 side. ``content`` carries the whole subtree."""

    content: Slot = ""


class BenchMulti(BaseComponent):
    """Sibling-list wrapper for a real builtin whose own template does a bare
    ``{{ content }}`` (no ``{% for %}``) — e.g. PJXCard's regions come from
    PJXCardHeader/Body/Footer rendered as one field's value (see
    pjx_card.py's own docstring), and the real test suite reaches for an
    ad hoc multi-slot host in exactly this situation
    (test_pjx_card.py's ``CardHost`` fixture). This is that host, generic and
    reused everywhere this fixture needs more than one sibling under a field
    whose template does not iterate its slot itself.
    """

    items: Slot = ""


def _multi(id_: str, items: list[BaseComponent]) -> BaseComponent:
    """``items[0]`` unwrapped when there is only one, else a BenchMulti host."""
    return items[0] if len(items) == 1 else BenchMulti(id=id_, items=items)


def _v2_display_primitives() -> list[BaseComponent]:
    return [
        PJXIcon(id="p-icon", name="settings"),
        PJXBadge(id="p-badge", label="new", color="brand"),
        PJXAvatar(id="p-avatar", initials="AB"),
        PJXAvatarStack(id="p-avatar-stack"),
        PJXDivider(id="p-divider"),
        PJXProgress(id="p-progress", value=42),
        PJXSkeleton(id="p-skeleton"),
        PJXSpinner(id="p-spinner"),
        PJXBreadcrumb(id="p-breadcrumb"),
    ]


def _v2_form_block() -> list[BaseComponent]:
    return [
        PJXFormField(
            id="f-password",
            content=PJXPasswordInput(id="pw-input", name="password"),
        ),
        PJXFormField(id="f-chip", content=PJXChipInput(id="chip-input", name="tags")),
        PJXSegmentedControl(id="f-segmented", name="mode"),
        PJXToggleSwitch(id="f-toggle", name="opt-in"),
        PJXButton(id="f-submit", type="submit", content="Save"),
    ]


def _v2_table(rows: int) -> PJXTable:
    header_cells = [
        PJXTableHeaderCell(id="hc-name", content="Name"),
        PJXTableHeaderCell(id="hc-value", content="Value"),
        PJXTableHeaderCell(id="hc-score", content="Score"),
    ]
    row_items = [
        PJXTableRow(
            id=f"r{r}",
            content=_multi(
                f"cells-r{r}",
                [
                    PJXTableCell(id=f"c{r}a", content=f"name {r}"),
                    PJXTableCell(
                        id=f"c{r}b", content=f'<input type="text" value="v{r}"/>'
                    ),
                    PJXTableCell(id=f"c{r}c", content=str(r * 3)),
                ],
            ),
        )
        for r in range(rows)
    ]
    return PJXTable(
        id="bench-table",
        content=_multi(
            "bench-table-sections",
            [
                PJXTableHead(
                    id="bench-thead",
                    content=PJXTableRow(
                        id="head-row", content=_multi("head-row-cells", header_cells)
                    ),
                ),
                PJXTableBody(
                    id="bench-tbody", content=_multi("bench-tbody-rows", row_items)
                ),
            ],
        ),
    )


def _v2_data_nav() -> list[BaseComponent]:
    return [
        PJXPaginator(
            id="bench-paginator", page=2, total_pages=10, url="/bench?page={page}"
        ),
        PJXRegionLoader(id="bench-region-loader"),
        PJXPageLoader(id="bench-page-loader"),
        PJXLazyLoad(id="bench-lazy-load", url="/bench/more"),
    ]


def _v2_shells(inner: list[BaseComponent]) -> PJXModal:
    """Modal -> Accordion -> TabGroup shell nest, wrapping ``inner``."""
    return PJXModal(
        id="bench-modal",
        content=_multi(
            "bench-modal-regions",
            [
                PJXModalHeader(id="bench-modal-header", content="Details"),
                PJXModalBody(
                    id="bench-modal-body",
                    content=PJXAccordionGroup(
                        id="bench-acc-group",
                        content=PJXAccordion(
                            id="bench-acc",
                            content=_multi(
                                "bench-acc-parts",
                                [
                                    PJXAccordionTrigger(
                                        id="bench-acc-trigger", content="Details"
                                    ),
                                    PJXAccordionContent(
                                        id="bench-acc-content",
                                        content=PJXTabGroup(
                                            id="bench-tabs",
                                            content=_multi(
                                                "bench-tabs-parts",
                                                [
                                                    PJXTabList(
                                                        id="bench-tab-list",
                                                        content=PJXTab(
                                                            id="bench-tab-1",
                                                            panel="bench-tab-panel-1",
                                                            content="Data",
                                                        ),
                                                    ),
                                                    PJXTabPanel(
                                                        id="bench-tab-panel-1",
                                                        content=_multi(
                                                            "bench-tab-panel-1-content",
                                                            inner,
                                                        ),
                                                    ),
                                                ],
                                            ),
                                        ),
                                    ),
                                ],
                            ),
                        ),
                    ),
                ),
                PJXModalFooter(id="bench-modal-footer", content="Close"),
            ],
        ),
    )


def _v2_cards_dropdown_popover_tooltip() -> list[BaseComponent]:
    return [
        PJXCard(
            id="bench-card",
            content=_multi(
                "bench-card-regions",
                [
                    PJXCardHeader(id="bench-card-header", content="Overview"),
                    PJXCardBody(id="bench-card-body", content="Summary text."),
                    PJXCardFooter(
                        id="bench-card-footer",
                        content=_multi(
                            "bench-card-footer-items",
                            [
                                PJXPopover(id="bench-popover"),
                                PJXDropdown(id="bench-dropdown", trigger="More"),
                                PJXTooltip(
                                    id="bench-tooltip",
                                    content=[
                                        PJXTooltipTrigger(
                                            id="bench-tooltip-trigger", content="?"
                                        ),
                                        PJXTooltipContent(
                                            id="bench-tooltip-content",
                                            content="Help text",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        ),
        PJXDrawer(
            id="bench-drawer",
            content=_multi(
                "bench-drawer-regions",
                [
                    PJXDrawerHeader(id="bench-drawer-header", content="Filters"),
                    PJXDrawerBody(id="bench-drawer-body", content="Body"),
                    PJXDrawerFooter(id="bench-drawer-footer", content="Close"),
                ],
            ),
        ),
    ]


def _v2_js_heavy_tail() -> list[BaseComponent]:
    return [
        PJXCarousel(
            id="bench-carousel",
            content=[
                PJXCarouselSlide(id="bench-slide-1", content="One"),
                PJXCarouselSlide(id="bench-slide-2", content="Two"),
            ],
        ),
        PJXNotification(id="bench-notification", content="Saved"),
        PJXToastHost(id="bench-toast-host"),
        PJXAlert(id="bench-alert", body="Heads up"),
        PJXResizableGroup(
            id="bench-resizable",
            content=[
                PJXResizablePanel(id="bench-resizable-panel-1", content="Left"),
                PJXResizableHandle(id="bench-resizable-handle"),
                PJXResizablePanel(id="bench-resizable-panel-2", content="Right"),
            ],
        ),
    ]


def build_v2_page(rows: int) -> BenchPage:
    """The full builtin-heavy page (v2 component tree, root: BenchPage)."""
    table_and_data: list[BaseComponent] = [_v2_table(rows), *_v2_data_nav()]
    body = [
        *_v2_display_primitives(),
        *_v2_form_block(),
        _v2_shells(table_and_data),
        *_v2_cards_dropdown_popover_tooltip(),
        *_v2_js_heavy_tail(),
    ]
    return BenchPage(id="bench-root", content=body)


def build_v2_table(rows: int) -> BenchPage:
    return BenchPage(id="bench-root", content=[_v2_table(rows), *_v2_data_nav()])


def build_v2_shells() -> BenchPage:
    return BenchPage(
        id="bench-root", content=_v2_shells(_v2_cards_dropdown_popover_tooltip())
    )
