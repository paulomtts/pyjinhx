"""Built-in components shipped with pyjinhx.

One directory per component: the module, its ``.pjx`` template and any
co-located asset live together so the descriptor's module-dir walk finds them
without configuration. This module re-exports every builtin's public class,
lazily, so callers can do ``from pyjinhx.builtins import PJXButton`` instead
of reaching into the individual component's submodule.
"""

from __future__ import annotations

import sys
import types
from typing import Any

__all__ = [  # noqa: RUF022
    "PJXAccordion",
    "PJXAccordionContent",
    "PJXAccordionGroup",
    "PJXAccordionTrigger",
    "PJXAlert",
    "PJXAvatar",
    "PJXAvatarStack",
    "PJXBadge",
    "PJXBreadcrumb",
    "PJXButton",
    "PJXCard",
    "PJXCardBody",
    "PJXCardFooter",
    "PJXCardHeader",
    "PJXCarousel",
    "PJXCarouselSlide",
    "PJXChart",
    "PJXChartSeries",
    "PJXChipInput",
    "PJXConfirmDialog",
    "PJXDivider",
    "PJXDrawer",
    "PJXDrawerBody",
    "PJXDrawerFooter",
    "PJXDrawerHeader",
    "PJXDropdown",
    "PJXEmptyState",
    "PJXFormField",
    "PJXGraph",
    "PJXGraphControls",
    "PJXGraphEdges",
    "PJXGraphNode",
    "PJXGraphNodes",
    "PJXGraphSidePanel",
    "PJXIcon",
    "PJXLazyLoad",
    "PJXModal",
    "PJXModalBody",
    "PJXModalFooter",
    "PJXModalHeader",
    "PJXNotification",
    "PJXPageLoader",
    "PJXPaginator",
    "PJXPasswordInput",
    "PJXPopover",
    "PJXPopoverPanel",
    "PJXPopoverTrigger",
    "PJXProgress",
    "PJXPromptDialog",
    "PJXRegionLoader",
    "PJXResizableGroup",
    "PJXResizableHandle",
    "PJXResizablePanel",
    "PJXRosterChip",
    "PJXRosterItem",
    "PJXRosterPicker",
    "PJXRosterResults",
    "PJXSegmentedControl",
    "PJXSelect",
    "PJXSkeleton",
    "PJXSpinner",
    "PJXStack",
    "PJXTab",
    "PJXTabGroup",
    "PJXTable",
    "PJXTableBody",
    "PJXTableCell",
    "PJXTableHead",
    "PJXTableHeaderCell",
    "PJXTableRow",
    "PJXTabList",
    "PJXTabPanel",
    "PJXToastHost",
    "PJXToggleSwitch",
    "PJXTooltip",
    "PJXTooltipContent",
    "PJXTooltipTrigger",
]

_lazy_imports = {
    "PJXAccordion": ("pyjinhx.builtins.pjx_accordion.pjx_accordion", "PJXAccordion"),
    "PJXAccordionContent": (
        "pyjinhx.builtins.pjx_accordion_content.pjx_accordion_content",
        "PJXAccordionContent",
    ),
    "PJXAccordionGroup": (
        "pyjinhx.builtins.pjx_accordion_group.pjx_accordion_group",
        "PJXAccordionGroup",
    ),
    "PJXAccordionTrigger": (
        "pyjinhx.builtins.pjx_accordion_trigger.pjx_accordion_trigger",
        "PJXAccordionTrigger",
    ),
    "PJXAlert": ("pyjinhx.builtins.pjx_alert.pjx_alert", "PJXAlert"),
    "PJXAvatar": ("pyjinhx.builtins.pjx_avatar.pjx_avatar", "PJXAvatar"),
    "PJXAvatarStack": (
        "pyjinhx.builtins.pjx_avatar_stack.pjx_avatar_stack",
        "PJXAvatarStack",
    ),
    "PJXBadge": ("pyjinhx.builtins.pjx_badge.pjx_badge", "PJXBadge"),
    "PJXBreadcrumb": (
        "pyjinhx.builtins.pjx_breadcrumb.pjx_breadcrumb",
        "PJXBreadcrumb",
    ),
    "PJXButton": ("pyjinhx.builtins.pjx_button.pjx_button", "PJXButton"),
    "PJXCard": ("pyjinhx.builtins.pjx_card.pjx_card", "PJXCard"),
    "PJXCardBody": ("pyjinhx.builtins.pjx_card_body.pjx_card_body", "PJXCardBody"),
    "PJXCardFooter": (
        "pyjinhx.builtins.pjx_card_footer.pjx_card_footer",
        "PJXCardFooter",
    ),
    "PJXCardHeader": (
        "pyjinhx.builtins.pjx_card_header.pjx_card_header",
        "PJXCardHeader",
    ),
    "PJXCarousel": ("pyjinhx.builtins.pjx_carousel.pjx_carousel", "PJXCarousel"),
    "PJXCarouselSlide": (
        "pyjinhx.builtins.pjx_carousel_slide.pjx_carousel_slide",
        "PJXCarouselSlide",
    ),
    "PJXChart": ("pyjinhx.builtins.pjx_chart.pjx_chart", "PJXChart"),
    "PJXChartSeries": ("pyjinhx.builtins.pjx_chart.series", "PJXChartSeries"),
    "PJXChipInput": (
        "pyjinhx.builtins.pjx_chip_input.pjx_chip_input",
        "PJXChipInput",
    ),
    "PJXConfirmDialog": (
        "pyjinhx.builtins.pjx_confirm_dialog.pjx_confirm_dialog",
        "PJXConfirmDialog",
    ),
    "PJXDivider": ("pyjinhx.builtins.pjx_divider.pjx_divider", "PJXDivider"),
    "PJXDrawer": ("pyjinhx.builtins.pjx_drawer.pjx_drawer", "PJXDrawer"),
    "PJXDrawerBody": (
        "pyjinhx.builtins.pjx_drawer_body.pjx_drawer_body",
        "PJXDrawerBody",
    ),
    "PJXDrawerFooter": (
        "pyjinhx.builtins.pjx_drawer_footer.pjx_drawer_footer",
        "PJXDrawerFooter",
    ),
    "PJXDrawerHeader": (
        "pyjinhx.builtins.pjx_drawer_header.pjx_drawer_header",
        "PJXDrawerHeader",
    ),
    "PJXDropdown": ("pyjinhx.builtins.pjx_dropdown.pjx_dropdown", "PJXDropdown"),
    "PJXEmptyState": (
        "pyjinhx.builtins.pjx_empty_state.pjx_empty_state",
        "PJXEmptyState",
    ),
    "PJXFormField": (
        "pyjinhx.builtins.pjx_form_field.pjx_form_field",
        "PJXFormField",
    ),
    "PJXGraph": ("pyjinhx.builtins.pjx_graph.pjx_graph", "PJXGraph"),
    "PJXGraphControls": (
        "pyjinhx.builtins.pjx_graph_controls.pjx_graph_controls",
        "PJXGraphControls",
    ),
    "PJXGraphEdges": (
        "pyjinhx.builtins.pjx_graph_edges.pjx_graph_edges",
        "PJXGraphEdges",
    ),
    "PJXGraphNode": (
        "pyjinhx.builtins.pjx_graph_node.pjx_graph_node",
        "PJXGraphNode",
    ),
    "PJXGraphNodes": (
        "pyjinhx.builtins.pjx_graph_nodes.pjx_graph_nodes",
        "PJXGraphNodes",
    ),
    "PJXGraphSidePanel": (
        "pyjinhx.builtins.pjx_graph_side_panel.pjx_graph_side_panel",
        "PJXGraphSidePanel",
    ),
    "PJXIcon": ("pyjinhx.builtins.pjx_icon.pjx_icon", "PJXIcon"),
    "PJXLazyLoad": ("pyjinhx.builtins.pjx_lazy_load.pjx_lazy_load", "PJXLazyLoad"),
    "PJXModal": ("pyjinhx.builtins.pjx_modal.pjx_modal", "PJXModal"),
    "PJXModalBody": (
        "pyjinhx.builtins.pjx_modal_body.pjx_modal_body",
        "PJXModalBody",
    ),
    "PJXModalFooter": (
        "pyjinhx.builtins.pjx_modal_footer.pjx_modal_footer",
        "PJXModalFooter",
    ),
    "PJXModalHeader": (
        "pyjinhx.builtins.pjx_modal_header.pjx_modal_header",
        "PJXModalHeader",
    ),
    "PJXNotification": (
        "pyjinhx.builtins.pjx_notification.pjx_notification",
        "PJXNotification",
    ),
    "PJXPageLoader": (
        "pyjinhx.builtins.pjx_page_loader.pjx_page_loader",
        "PJXPageLoader",
    ),
    "PJXPaginator": ("pyjinhx.builtins.pjx_paginator.pjx_paginator", "PJXPaginator"),
    "PJXPasswordInput": (
        "pyjinhx.builtins.pjx_password_input.pjx_password_input",
        "PJXPasswordInput",
    ),
    "PJXPopover": ("pyjinhx.builtins.pjx_popover.pjx_popover", "PJXPopover"),
    "PJXPopoverPanel": (
        "pyjinhx.builtins.pjx_popover_panel.pjx_popover_panel",
        "PJXPopoverPanel",
    ),
    "PJXPopoverTrigger": (
        "pyjinhx.builtins.pjx_popover_trigger.pjx_popover_trigger",
        "PJXPopoverTrigger",
    ),
    "PJXProgress": ("pyjinhx.builtins.pjx_progress.pjx_progress", "PJXProgress"),
    "PJXPromptDialog": (
        "pyjinhx.builtins.pjx_prompt_dialog.pjx_prompt_dialog",
        "PJXPromptDialog",
    ),
    "PJXRegionLoader": (
        "pyjinhx.builtins.pjx_region_loader.pjx_region_loader",
        "PJXRegionLoader",
    ),
    "PJXResizableGroup": (
        "pyjinhx.builtins.pjx_resizable_group.pjx_resizable_group",
        "PJXResizableGroup",
    ),
    "PJXResizableHandle": (
        "pyjinhx.builtins.pjx_resizable_handle.pjx_resizable_handle",
        "PJXResizableHandle",
    ),
    "PJXResizablePanel": (
        "pyjinhx.builtins.pjx_resizable_panel.pjx_resizable_panel",
        "PJXResizablePanel",
    ),
    "PJXRosterChip": (
        "pyjinhx.builtins.pjx_roster_chip.pjx_roster_chip",
        "PJXRosterChip",
    ),
    "PJXRosterItem": ("pyjinhx.builtins.pjx_roster_picker.item", "PJXRosterItem"),
    "PJXRosterPicker": (
        "pyjinhx.builtins.pjx_roster_picker.pjx_roster_picker",
        "PJXRosterPicker",
    ),
    "PJXRosterResults": (
        "pyjinhx.builtins.pjx_roster_results.pjx_roster_results",
        "PJXRosterResults",
    ),
    "PJXSegmentedControl": (
        "pyjinhx.builtins.pjx_segmented_control.pjx_segmented_control",
        "PJXSegmentedControl",
    ),
    "PJXSelect": ("pyjinhx.builtins.pjx_select.pjx_select", "PJXSelect"),
    "PJXSkeleton": ("pyjinhx.builtins.pjx_skeleton.pjx_skeleton", "PJXSkeleton"),
    "PJXSpinner": ("pyjinhx.builtins.pjx_spinner.pjx_spinner", "PJXSpinner"),
    "PJXStack": ("pyjinhx.builtins.pjx_stack.pjx_stack", "PJXStack"),
    "PJXTab": ("pyjinhx.builtins.pjx_tab.pjx_tab", "PJXTab"),
    "PJXTabGroup": ("pyjinhx.builtins.pjx_tab_group.pjx_tab_group", "PJXTabGroup"),
    "PJXTable": ("pyjinhx.builtins.pjx_table.pjx_table", "PJXTable"),
    "PJXTableBody": ("pyjinhx.builtins.pjx_table_body.pjx_table_body", "PJXTableBody"),
    "PJXTableCell": ("pyjinhx.builtins.pjx_table_cell.pjx_table_cell", "PJXTableCell"),
    "PJXTableHead": ("pyjinhx.builtins.pjx_table_head.pjx_table_head", "PJXTableHead"),
    "PJXTableHeaderCell": (
        "pyjinhx.builtins.pjx_table_header_cell.pjx_table_header_cell",
        "PJXTableHeaderCell",
    ),
    "PJXTableRow": ("pyjinhx.builtins.pjx_table_row.pjx_table_row", "PJXTableRow"),
    "PJXTabList": ("pyjinhx.builtins.pjx_tab_list.pjx_tab_list", "PJXTabList"),
    "PJXTabPanel": ("pyjinhx.builtins.pjx_tab_panel.pjx_tab_panel", "PJXTabPanel"),
    "PJXToastHost": (
        "pyjinhx.builtins.pjx_toast_host.pjx_toast_host",
        "PJXToastHost",
    ),
    "PJXToggleSwitch": (
        "pyjinhx.builtins.pjx_toggle_switch.pjx_toggle_switch",
        "PJXToggleSwitch",
    ),
    "PJXTooltip": ("pyjinhx.builtins.pjx_tooltip.pjx_tooltip", "PJXTooltip"),
    "PJXTooltipContent": (
        "pyjinhx.builtins.pjx_tooltip_content.pjx_tooltip_content",
        "PJXTooltipContent",
    ),
    "PJXTooltipTrigger": (
        "pyjinhx.builtins.pjx_tooltip_trigger.pjx_tooltip_trigger",
        "PJXTooltipTrigger",
    ),
}

_cached_imports: dict[str, Any] = {}


class _PyjinhxBuiltinsModule(types.ModuleType):
    """Custom module that provides lazy-loaded builtin exports."""

    def __getattr__(self, name: str) -> Any:
        """Lazy-load builtin exports on demand."""
        if name in _lazy_imports:
            if name in _cached_imports:
                return _cached_imports[name]

            module_name, attr_name = _lazy_imports[name]
            module = __import__(module_name, fromlist=[attr_name])
            result = getattr(module, attr_name)

            _cached_imports[name] = result
            return result

        raise AttributeError(f"module {self.__name__!r} has no attribute {name!r}")


_current_module = sys.modules[__name__]
_new_module = _PyjinhxBuiltinsModule(__name__)
_new_module.__dict__.update(_current_module.__dict__)
sys.modules[__name__] = _new_module
