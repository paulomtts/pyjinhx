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
    "PJXChipInput",
    "PJXDivider",
    "PJXDrawer",
    "PJXDrawerBody",
    "PJXDrawerFooter",
    "PJXDrawerHeader",
    "PJXDropdown",
    "PJXEmptyState",
    "PJXFormField",
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
    "PJXRegionLoader",
    "PJXResizableGroup",
    "PJXResizableHandle",
    "PJXResizablePanel",
    "PJXSegmentedControl",
    "PJXSkeleton",
    "PJXSpinner",
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
    "PJXAccordion": ("pyjinhx.builtins.ui.pjx_accordion.pjx_accordion", "PJXAccordion"),
    "PJXAccordionContent": (
        "pyjinhx.builtins.ui.pjx_accordion_content.pjx_accordion_content",
        "PJXAccordionContent",
    ),
    "PJXAccordionGroup": (
        "pyjinhx.builtins.ui.pjx_accordion_group.pjx_accordion_group",
        "PJXAccordionGroup",
    ),
    "PJXAccordionTrigger": (
        "pyjinhx.builtins.ui.pjx_accordion_trigger.pjx_accordion_trigger",
        "PJXAccordionTrigger",
    ),
    "PJXAlert": ("pyjinhx.builtins.ui.pjx_alert.pjx_alert", "PJXAlert"),
    "PJXAvatar": ("pyjinhx.builtins.ui.pjx_avatar.pjx_avatar", "PJXAvatar"),
    "PJXAvatarStack": (
        "pyjinhx.builtins.ui.pjx_avatar_stack.pjx_avatar_stack",
        "PJXAvatarStack",
    ),
    "PJXBadge": ("pyjinhx.builtins.ui.pjx_badge.pjx_badge", "PJXBadge"),
    "PJXBreadcrumb": (
        "pyjinhx.builtins.ui.pjx_breadcrumb.pjx_breadcrumb",
        "PJXBreadcrumb",
    ),
    "PJXButton": ("pyjinhx.builtins.ui.pjx_button.pjx_button", "PJXButton"),
    "PJXCard": ("pyjinhx.builtins.ui.pjx_card.pjx_card", "PJXCard"),
    "PJXCardBody": ("pyjinhx.builtins.ui.pjx_card_body.pjx_card_body", "PJXCardBody"),
    "PJXCardFooter": (
        "pyjinhx.builtins.ui.pjx_card_footer.pjx_card_footer",
        "PJXCardFooter",
    ),
    "PJXCardHeader": (
        "pyjinhx.builtins.ui.pjx_card_header.pjx_card_header",
        "PJXCardHeader",
    ),
    "PJXCarousel": ("pyjinhx.builtins.ui.pjx_carousel.pjx_carousel", "PJXCarousel"),
    "PJXCarouselSlide": (
        "pyjinhx.builtins.ui.pjx_carousel_slide.pjx_carousel_slide",
        "PJXCarouselSlide",
    ),
    "PJXChipInput": (
        "pyjinhx.builtins.ui.pjx_chip_input.pjx_chip_input",
        "PJXChipInput",
    ),
    "PJXDivider": ("pyjinhx.builtins.ui.pjx_divider.pjx_divider", "PJXDivider"),
    "PJXDrawer": ("pyjinhx.builtins.ui.pjx_drawer.pjx_drawer", "PJXDrawer"),
    "PJXDrawerBody": (
        "pyjinhx.builtins.ui.pjx_drawer_body.pjx_drawer_body",
        "PJXDrawerBody",
    ),
    "PJXDrawerFooter": (
        "pyjinhx.builtins.ui.pjx_drawer_footer.pjx_drawer_footer",
        "PJXDrawerFooter",
    ),
    "PJXDrawerHeader": (
        "pyjinhx.builtins.ui.pjx_drawer_header.pjx_drawer_header",
        "PJXDrawerHeader",
    ),
    "PJXDropdown": ("pyjinhx.builtins.ui.pjx_dropdown.pjx_dropdown", "PJXDropdown"),
    "PJXEmptyState": (
        "pyjinhx.builtins.ui.pjx_empty_state.pjx_empty_state",
        "PJXEmptyState",
    ),
    "PJXFormField": (
        "pyjinhx.builtins.ui.pjx_form_field.pjx_form_field",
        "PJXFormField",
    ),
    "PJXIcon": ("pyjinhx.builtins.ui.pjx_icon.pjx_icon", "PJXIcon"),
    "PJXLazyLoad": ("pyjinhx.builtins.pjx_lazy_load.pjx_lazy_load", "PJXLazyLoad"),
    "PJXModal": ("pyjinhx.builtins.ui.pjx_modal.pjx_modal", "PJXModal"),
    "PJXModalBody": (
        "pyjinhx.builtins.ui.pjx_modal_body.pjx_modal_body",
        "PJXModalBody",
    ),
    "PJXModalFooter": (
        "pyjinhx.builtins.ui.pjx_modal_footer.pjx_modal_footer",
        "PJXModalFooter",
    ),
    "PJXModalHeader": (
        "pyjinhx.builtins.ui.pjx_modal_header.pjx_modal_header",
        "PJXModalHeader",
    ),
    "PJXNotification": (
        "pyjinhx.builtins.ui.pjx_notification.pjx_notification",
        "PJXNotification",
    ),
    "PJXPageLoader": (
        "pyjinhx.builtins.pjx_page_loader.pjx_page_loader",
        "PJXPageLoader",
    ),
    "PJXPaginator": ("pyjinhx.builtins.pjx_paginator.pjx_paginator", "PJXPaginator"),
    "PJXPasswordInput": (
        "pyjinhx.builtins.ui.pjx_password_input.pjx_password_input",
        "PJXPasswordInput",
    ),
    "PJXPopover": ("pyjinhx.builtins.ui.pjx_popover.pjx_popover", "PJXPopover"),
    "PJXPopoverPanel": (
        "pyjinhx.builtins.ui.pjx_popover_panel.pjx_popover_panel",
        "PJXPopoverPanel",
    ),
    "PJXPopoverTrigger": (
        "pyjinhx.builtins.ui.pjx_popover_trigger.pjx_popover_trigger",
        "PJXPopoverTrigger",
    ),
    "PJXProgress": ("pyjinhx.builtins.ui.pjx_progress.pjx_progress", "PJXProgress"),
    "PJXRegionLoader": (
        "pyjinhx.builtins.pjx_region_loader.pjx_region_loader",
        "PJXRegionLoader",
    ),
    "PJXResizableGroup": (
        "pyjinhx.builtins.ui.pjx_resizable_group.pjx_resizable_group",
        "PJXResizableGroup",
    ),
    "PJXResizableHandle": (
        "pyjinhx.builtins.ui.pjx_resizable_handle.pjx_resizable_handle",
        "PJXResizableHandle",
    ),
    "PJXResizablePanel": (
        "pyjinhx.builtins.ui.pjx_resizable_panel.pjx_resizable_panel",
        "PJXResizablePanel",
    ),
    "PJXSegmentedControl": (
        "pyjinhx.builtins.ui.pjx_segmented_control.pjx_segmented_control",
        "PJXSegmentedControl",
    ),
    "PJXSkeleton": ("pyjinhx.builtins.ui.pjx_skeleton.pjx_skeleton", "PJXSkeleton"),
    "PJXSpinner": ("pyjinhx.builtins.ui.pjx_spinner.pjx_spinner", "PJXSpinner"),
    "PJXTab": ("pyjinhx.builtins.ui.pjx_tab.pjx_tab", "PJXTab"),
    "PJXTabGroup": ("pyjinhx.builtins.ui.pjx_tab_group.pjx_tab_group", "PJXTabGroup"),
    "PJXTable": ("pyjinhx.builtins.pjx_table.pjx_table", "PJXTable"),
    "PJXTableBody": ("pyjinhx.builtins.pjx_table_body.pjx_table_body", "PJXTableBody"),
    "PJXTableCell": ("pyjinhx.builtins.pjx_table_cell.pjx_table_cell", "PJXTableCell"),
    "PJXTableHead": ("pyjinhx.builtins.pjx_table_head.pjx_table_head", "PJXTableHead"),
    "PJXTableHeaderCell": (
        "pyjinhx.builtins.pjx_table_header_cell.pjx_table_header_cell",
        "PJXTableHeaderCell",
    ),
    "PJXTableRow": ("pyjinhx.builtins.pjx_table_row.pjx_table_row", "PJXTableRow"),
    "PJXTabList": ("pyjinhx.builtins.ui.pjx_tab_list.pjx_tab_list", "PJXTabList"),
    "PJXTabPanel": ("pyjinhx.builtins.ui.pjx_tab_panel.pjx_tab_panel", "PJXTabPanel"),
    "PJXToastHost": (
        "pyjinhx.builtins.ui.pjx_toast_host.pjx_toast_host",
        "PJXToastHost",
    ),
    "PJXToggleSwitch": (
        "pyjinhx.builtins.ui.pjx_toggle_switch.pjx_toggle_switch",
        "PJXToggleSwitch",
    ),
    "PJXTooltip": ("pyjinhx.builtins.ui.pjx_tooltip.pjx_tooltip", "PJXTooltip"),
    "PJXTooltipContent": (
        "pyjinhx.builtins.ui.pjx_tooltip_content.pjx_tooltip_content",
        "PJXTooltipContent",
    ),
    "PJXTooltipTrigger": (
        "pyjinhx.builtins.ui.pjx_tooltip_trigger.pjx_tooltip_trigger",
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
