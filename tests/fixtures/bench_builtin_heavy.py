"""Shared "builtin-heavy page" used by scripts/bench_v0_vs_v2.py (issue #537).

One composition covering all five L4 builtin families, expressed twice —
once against pyjinhx v0.36.4 tags, once against pyjinhx2 tags — so the two
renderers are timed on the same page. Both packages happen to spell every
shared builtin's tag identically (PascalCase class name, e.g. ``PJXTable``),
so ``TAGS`` maps every logical name to the *same* string on both sides today;
the mapping still exists so a future rename during the port stays visible in
one place instead of silently skewing the bench.

Excluded builtins (present in v0.36.4 but not ported to v2, so dropped from
BOTH sides to keep the comparison 1:1 — confirmed via
``diff <(ls pyjinhx/builtins/ui) <(ls pyjinhx2/builtins/ui)`` against the
v0.36.4 tag, issue #537 Task 0): see EXCLUDED_FROM_BOTH below.

v2 also splits ``PJXPopover`` into a trigger/panel pair
(``PJXPopoverTrigger``/``PJXPopoverPanel``) that v0.36.4 does not have; this
fixture uses only the bare, self-closing ``PJXPopover`` root on both sides so
the page stays expressible identically without inventing v0-side children
that were never ported.
"""

EXCLUDED_FROM_BOTH = (
    "PJXConfirmDialog",
    "PJXPromptDialog",
)

# Logical name -> (v0.36 tag, v2 tag). Identical today; the mapping exists so
# a rename during the port stays visible instead of silently skewing the bench.
TAGS: dict[str, tuple[str, str]] = {
    # Display primitives (L4.1)
    "icon": ("PJXIcon", "PJXIcon"),
    "badge": ("PJXBadge", "PJXBadge"),
    "avatar": ("PJXAvatar", "PJXAvatar"),
    "avatar_stack": ("PJXAvatarStack", "PJXAvatarStack"),
    "divider": ("PJXDivider", "PJXDivider"),
    "progress": ("PJXProgress", "PJXProgress"),
    "skeleton": ("PJXSkeleton", "PJXSkeleton"),
    "spinner": ("PJXSpinner", "PJXSpinner"),
    "breadcrumb": ("PJXBreadcrumb", "PJXBreadcrumb"),
    # Forms (L4.2)
    "button": ("PJXButton", "PJXButton"),
    "form_field": ("PJXFormField", "PJXFormField"),
    "password_input": ("PJXPasswordInput", "PJXPasswordInput"),
    "chip_input": ("PJXChipInput", "PJXChipInput"),
    "segmented_control": ("PJXSegmentedControl", "PJXSegmentedControl"),
    "toggle_switch": ("PJXToggleSwitch", "PJXToggleSwitch"),
    # Composed shells (L4.3)
    "card": ("PJXCard", "PJXCard"),
    "card_header": ("PJXCardHeader", "PJXCardHeader"),
    "card_body": ("PJXCardBody", "PJXCardBody"),
    "card_footer": ("PJXCardFooter", "PJXCardFooter"),
    "modal": ("PJXModal", "PJXModal"),
    "modal_header": ("PJXModalHeader", "PJXModalHeader"),
    "modal_body": ("PJXModalBody", "PJXModalBody"),
    "modal_footer": ("PJXModalFooter", "PJXModalFooter"),
    "drawer": ("PJXDrawer", "PJXDrawer"),
    "drawer_header": ("PJXDrawerHeader", "PJXDrawerHeader"),
    "drawer_body": ("PJXDrawerBody", "PJXDrawerBody"),
    "drawer_footer": ("PJXDrawerFooter", "PJXDrawerFooter"),
    "accordion": ("PJXAccordion", "PJXAccordion"),
    "accordion_group": ("PJXAccordionGroup", "PJXAccordionGroup"),
    "accordion_trigger": ("PJXAccordionTrigger", "PJXAccordionTrigger"),
    "accordion_content": ("PJXAccordionContent", "PJXAccordionContent"),
    "tab": ("PJXTab", "PJXTab"),
    "tab_group": ("PJXTabGroup", "PJXTabGroup"),
    "tab_list": ("PJXTabList", "PJXTabList"),
    "tab_panel": ("PJXTabPanel", "PJXTabPanel"),
    "popover": ("PJXPopover", "PJXPopover"),
    "dropdown": ("PJXDropdown", "PJXDropdown"),
    "tooltip": ("PJXTooltip", "PJXTooltip"),
    "tooltip_trigger": ("PJXTooltipTrigger", "PJXTooltipTrigger"),
    "tooltip_content": ("PJXTooltipContent", "PJXTooltipContent"),
    # Table / paginator / loaders (L4.4)
    "table": ("PJXTable", "PJXTable"),
    "table_body": ("PJXTableBody", "PJXTableBody"),
    "table_head": ("PJXTableHead", "PJXTableHead"),
    "table_header_cell": ("PJXTableHeaderCell", "PJXTableHeaderCell"),
    "table_row": ("PJXTableRow", "PJXTableRow"),
    "table_cell": ("PJXTableCell", "PJXTableCell"),
    "paginator": ("PJXPaginator", "PJXPaginator"),
    "region_loader": ("PJXRegionLoader", "PJXRegionLoader"),
    "page_loader": ("PJXPageLoader", "PJXPageLoader"),
    "lazy_load": ("PJXLazyLoad", "PJXLazyLoad"),
    # JS-heavy tail (L4.5)
    "carousel": ("PJXCarousel", "PJXCarousel"),
    "carousel_slide": ("PJXCarouselSlide", "PJXCarouselSlide"),
    "notification": ("PJXNotification", "PJXNotification"),
    "toast_host": ("PJXToastHost", "PJXToastHost"),
    "alert": ("PJXAlert", "PJXAlert"),
    "resizable_group": ("PJXResizableGroup", "PJXResizableGroup"),
    "resizable_handle": ("PJXResizableHandle", "PJXResizableHandle"),
    "resizable_panel": ("PJXResizablePanel", "PJXResizablePanel"),
}

V0_MANIFEST = [v0 for v0, _ in TAGS.values()]
V2_MANIFEST = [v2 for _, v2 in TAGS.values()]

V0_SIDE = 0
V2_SIDE = 1


def _tag(logical: str, side: int) -> str:
    return TAGS[logical][side]


def _display_primitives(side: int) -> str:
    return (
        f'<{_tag("icon", side)} id="p-icon" name="gear"/>'
        f'<{_tag("badge", side)} id="p-badge" label="new" color="brand"/>'
        f'<{_tag("avatar", side)} id="p-avatar" initials="AB"/>'
        f'<{_tag("avatar_stack", side)} id="p-avatar-stack"/>'
        f'<{_tag("divider", side)} id="p-divider"/>'
        f'<{_tag("progress", side)} id="p-progress" value="42"/>'
        f'<{_tag("skeleton", side)} id="p-skeleton"/>'
        f'<{_tag("spinner", side)} id="p-spinner"/>'
        f'<{_tag("breadcrumb", side)} id="p-breadcrumb"/>'
    )


def _form_block(side: int) -> str:
    ff, pw, chip, seg, tog, btn = (
        _tag("form_field", side),
        _tag("password_input", side),
        _tag("chip_input", side),
        _tag("segmented_control", side),
        _tag("toggle_switch", side),
        _tag("button", side),
    )
    return (
        f'<{ff} id="f-password"><{pw} id="pw-input" name="password"/></{ff}>'
        f'<{ff} id="f-chip"><{chip} id="chip-input" name="tags"/></{ff}>'
        f'<{seg} id="f-segmented" name="mode"/>'
        f'<{tog} id="f-toggle" name="opt-in"/>'
        f'<{btn} id="f-submit" type="submit">Save</{btn}>'
    )


def _table(rows: int, side: int) -> str:
    t, tb, th, thc, tr, td = (
        _tag("table", side),
        _tag("table_body", side),
        _tag("table_head", side),
        _tag("table_header_cell", side),
        _tag("table_row", side),
        _tag("table_cell", side),
    )
    parts = [
        f'<{t} id="bench-table">'
        f'<{th} id="bench-thead"><{tr} id="head-row">'
        f'<{thc} id="hc-name">Name</{thc}>'
        f'<{thc} id="hc-value">Value</{thc}>'
        f'<{thc} id="hc-score">Score</{thc}>'
        f"</{tr}></{th}>"
        f'<{tb} id="bench-tbody">'
    ]
    for r in range(rows):
        parts.append(
            f'<{tr} id="r{r}">'
            f'<{td} id="c{r}a">name {r}</{td}>'
            f'<{td} id="c{r}b"><input type="text" value="v{r}"/></{td}>'
            f'<{td} id="c{r}c">{r * 3}</{td}>'
            f"</{tr}>"
        )
    parts.append(f"</{tb}></{t}>")
    return "".join(parts)


def _shells(inner: str, side: int) -> str:
    """Modal -> Accordion -> TabGroup shell nest, wrapping ``inner``."""
    (
        modal,
        modal_header,
        modal_body,
        modal_footer,
        acc_group,
        acc,
        acc_trigger,
        acc_content,
        tab_group,
        tab_list,
        tab,
        tab_panel,
    ) = (
        _tag("modal", side),
        _tag("modal_header", side),
        _tag("modal_body", side),
        _tag("modal_footer", side),
        _tag("accordion_group", side),
        _tag("accordion", side),
        _tag("accordion_trigger", side),
        _tag("accordion_content", side),
        _tag("tab_group", side),
        _tag("tab_list", side),
        _tag("tab", side),
        _tag("tab_panel", side),
    )
    return (
        f'<{modal} id="bench-modal">'
        f'<{modal_header} id="bench-modal-header">Details</{modal_header}>'
        f'<{modal_body} id="bench-modal-body">'
        f'<{acc_group} id="bench-acc-group">'
        f'<{acc} id="bench-acc">'
        f'<{acc_trigger} id="bench-acc-trigger">Details</{acc_trigger}>'
        f'<{acc_content} id="bench-acc-content">'
        f'<{tab_group} id="bench-tabs">'
        f'<{tab_list} id="bench-tab-list">'
        f'<{tab} id="bench-tab-1" panel="bench-tab-panel-1">Data</{tab}>'
        f"</{tab_list}>"
        f'<{tab_panel} id="bench-tab-panel-1">{inner}</{tab_panel}>'
        f"</{tab_group}>"
        f"</{acc_content}>"
        f"</{acc}>"
        f"</{acc_group}>"
        f"</{modal_body}>"
        f'<{modal_footer} id="bench-modal-footer">Close</{modal_footer}>'
        f"</{modal}>"
    )


def _cards_dropdown_popover_tooltip(side: int) -> str:
    (
        card,
        card_header,
        card_body,
        card_footer,
        drawer,
        drawer_header,
        drawer_body,
        drawer_footer,
        popover,
        dropdown,
        tooltip,
        tooltip_trigger,
        tooltip_content,
    ) = (
        _tag("card", side),
        _tag("card_header", side),
        _tag("card_body", side),
        _tag("card_footer", side),
        _tag("drawer", side),
        _tag("drawer_header", side),
        _tag("drawer_body", side),
        _tag("drawer_footer", side),
        _tag("popover", side),
        _tag("dropdown", side),
        _tag("tooltip", side),
        _tag("tooltip_trigger", side),
        _tag("tooltip_content", side),
    )
    return (
        f'<{card} id="bench-card">'
        f'<{card_header} id="bench-card-header">Overview</{card_header}>'
        f'<{card_body} id="bench-card-body">Summary text.</{card_body}>'
        f'<{card_footer} id="bench-card-footer">'
        f'<{popover} id="bench-popover"/>'
        f'<{dropdown} id="bench-dropdown" trigger="More"/>'
        f'<{tooltip} id="bench-tooltip">'
        f'<{tooltip_trigger} id="bench-tooltip-trigger">?</{tooltip_trigger}>'
        f'<{tooltip_content} id="bench-tooltip-content">Help text</{tooltip_content}>'
        f"</{tooltip}>"
        f"</{card_footer}>"
        f"</{card}>"
        f'<{drawer} id="bench-drawer">'
        f'<{drawer_header} id="bench-drawer-header">Filters</{drawer_header}>'
        f'<{drawer_body} id="bench-drawer-body">Body</{drawer_body}>'
        f'<{drawer_footer} id="bench-drawer-footer">Close</{drawer_footer}>'
        f"</{drawer}>"
    )


def _data_nav(side: int) -> str:
    pag, region, page, lazy = (
        _tag("paginator", side),
        _tag("region_loader", side),
        _tag("page_loader", side),
        _tag("lazy_load", side),
    )
    return (
        f'<{pag} id="bench-paginator" page="2" total_pages="10" url="/bench"/>'
        f'<{region} id="bench-region-loader"/>'
        f'<{page} id="bench-page-loader"/>'
        f'<{lazy} id="bench-lazy-load" url="/bench/more"/>'
    )


def _js_heavy_tail(side: int) -> str:
    (
        carousel,
        slide,
        notification,
        toast_host,
        alert,
        resizable_group,
        resizable_handle,
        resizable_panel,
    ) = (
        _tag("carousel", side),
        _tag("carousel_slide", side),
        _tag("notification", side),
        _tag("toast_host", side),
        _tag("alert", side),
        _tag("resizable_group", side),
        _tag("resizable_handle", side),
        _tag("resizable_panel", side),
    )
    return (
        f'<{carousel} id="bench-carousel">'
        f'<{slide} id="bench-slide-1">One</{slide}>'
        f'<{slide} id="bench-slide-2">Two</{slide}>'
        f"</{carousel}>"
        f'<{notification} id="bench-notification">Saved</{notification}>'
        f'<{toast_host} id="bench-toast-host"/>'
        f'<{alert} id="bench-alert">Heads up</{alert}>'
        f'<{resizable_group} id="bench-resizable">'
        f'<{resizable_panel} id="bench-resizable-panel-1">Left</{resizable_panel}>'
        f'<{resizable_handle} id="bench-resizable-handle"/>'
        f'<{resizable_panel} id="bench-resizable-panel-2">Right</{resizable_panel}>'
        f"</{resizable_group}>"
    )


def _page(rows: int, side: int) -> str:
    """The full builtin-heavy page: one composition spanning all five L4 families."""
    table_and_data = _table(rows, side) + _data_nav(side)
    body = (
        _display_primitives(side)
        + _form_block(side)
        + _shells(table_and_data, side)
        + _cards_dropdown_popover_tooltip(side)
        + _js_heavy_tail(side)
    )
    return f'<div id="bench-root">{body}</div>'


def build_v0_page(rows: int) -> str:
    return _page(rows, V0_SIDE)


def build_v2_page(rows: int) -> str:
    return _page(rows, V2_SIDE)


def build_v0_table(rows: int) -> str:
    return _table(rows, V0_SIDE) + _data_nav(V0_SIDE)


def build_v2_table(rows: int) -> str:
    return _table(rows, V2_SIDE) + _data_nav(V2_SIDE)


def build_v0_shells() -> str:
    return _shells(_cards_dropdown_popover_tooltip(V0_SIDE), V0_SIDE)


def build_v2_shells() -> str:
    return _shells(_cards_dropdown_popover_tooltip(V2_SIDE), V2_SIDE)
