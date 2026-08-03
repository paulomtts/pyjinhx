from pyjinhx.builtins.ui.pjx_alert import PJXAlert
from pyjinhx.builtins.ui.pjx_drawer import PJXDrawer
from pyjinhx.builtins.ui.pjx_drawer_body import PJXDrawerBody
from pyjinhx.builtins.ui.pjx_drawer_footer import PJXDrawerFooter
from pyjinhx.builtins.ui.pjx_drawer_header import PJXDrawerHeader
from pyjinhx.builtins.ui.pjx_modal import PJXModal
from pyjinhx.builtins.ui.pjx_modal_body import PJXModalBody
from pyjinhx.builtins.ui.pjx_modal_footer import PJXModalFooter
from pyjinhx.builtins.ui.pjx_modal_header import PJXModalHeader
from pyjinhx.builtins.ui.pjx_notification import PJXNotification
from pyjinhx.builtins.ui.pjx_popover import PJXPopover
from pyjinhx.builtins.ui.pjx_popover_panel import PJXPopoverPanel
from pyjinhx.builtins.ui.pjx_popover_trigger import PJXPopoverTrigger
from pyjinhx.builtins.ui.pjx_tooltip import PJXTooltip
from pyjinhx.builtins.ui.pjx_tooltip_content import PJXTooltipContent
from pyjinhx.builtins.ui.pjx_tooltip_trigger import PJXTooltipTrigger


def modal():
    return [
        '<button class="pjx-demo-btn" data-pjx-open="demo-modal">Open modal</button>',
        PJXModal(
            id="demo-modal",
            content=(
                str(PJXModalHeader(id="demo-modal-h", title="Confirm changes").render())
                + str(
                    PJXModalBody(
                        id="demo-modal-b",
                        content="Your draft will be published immediately. This action cannot be undone.",
                    ).render()
                )
                + str(
                    PJXModalFooter(
                        id="demo-modal-f",
                        content='<button class="pjx-demo-btn" data-pjx-close>Cancel</button>',
                    ).render()
                )
            ),
        ).render(),
    ]


def drawer():
    return [
        '<button class="pjx-demo-btn" data-pjx-open="demo-drawer">Open drawer</button>',
        PJXDrawer(
            id="demo-drawer",
            side="right",
            content=(
                PJXDrawerHeader(id="demo-drawer-h", title="Filter results").render()
                + PJXDrawerBody(
                    id="demo-drawer-b",
                    content="<p>Adjust filters to narrow down your results.</p>",
                ).render()
                + PJXDrawerFooter(
                    id="demo-drawer-f",
                    content='<button class="pjx-demo-btn" data-pjx-close>Done</button>',
                ).render()
            ),
        ).render(),
    ]


def notification():
    return [
        PJXNotification(
            id="demo-notification",
            content="Your changes have been saved.",
            corner="top-right",
            timeout=4000,
        ).render(),
        (
            '<button class="pjx-demo-btn" onclick="pjx.notification.show(\'demo-notification\')">'
            "Show notification</button>"
        ),
    ]


def alert():
    return [
        PJXAlert(
            variant="info", title="Heads up", body="A new version is available."
        ).render(),
        PJXAlert(variant="success", body="Your changes were saved.").render(),
        PJXAlert(variant="warning", body="Your session expires in 5 minutes.").render(),
        PJXAlert(
            variant="error", body="Could not reach the server.", dismissible=True
        ).render(),
    ]


def tooltip():
    return PJXTooltip(
        id="demo-tooltip",
        placement="top",
        content=(
            str(
                PJXTooltipTrigger(
                    id="demo-tooltip-tr", content="Hover over me"
                ).render()
            )
            + str(
                PJXTooltipContent(
                    id="demo-tooltip-tc",
                    content="This is additional context shown on hover or focus.",
                ).render()
            )
        ),
    ).render()


def popover():
    return PJXPopover(
        id="demo-popover",
        content=(
            PJXPopoverTrigger(
                id="demo-popover-t", content="Show info", role="dialog"
            ).render()
            + PJXPopoverPanel(
                id="demo-popover-p",
                role="dialog",
                content=(
                    "<strong>Keyboard shortcuts</strong>"
                    '<p style="margin:.35rem 0 0">Press <kbd>?</kbd> anytime to reopen this panel.</p>'
                ),
            ).render()
        ),
    ).render()


DEMOS = {
    "PJXModal": (modal, 520),
    "PJXDrawer": (drawer, 420),
    "PJXNotification": (notification, 140),
    "PJXAlert": (alert, 280),
    "PJXTooltip": (tooltip, 160),
    "PJXPopover": (popover, 320),
}
