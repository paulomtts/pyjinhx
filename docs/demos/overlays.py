from pyjinhx.builtins import (
    PJXAlert,
    PJXConfirmDialog,
    PJXDrawer,
    PJXModal,
    PJXModalBody,
    PJXModalFooter,
    PJXModalHeader,
    PJXNotification,
    PJXPopover,
    PJXPopoverPanel,
    PJXPopoverTrigger,
    PJXPromptDialog,
    PJXTooltip,
)


def modal():
    return [
        '<button class="pjx-demo-btn" data-pjx-open="demo-modal">Open modal</button>',
        PJXModal(
            id="demo-modal",
            content=(
                str(PJXModalHeader(id="demo-modal-h", title="Confirm changes").render())
                + str(PJXModalBody(id="demo-modal-b", content="Your draft will be published immediately. This action cannot be undone.").render())
                + str(PJXModalFooter(id="demo-modal-f", content='<button class="pjx-demo-btn" data-pjx-close>Cancel</button>').render())
            ),
        ).render(),
    ]


def drawer():
    return [
        '<button class="pjx-demo-btn" data-pjx-open="demo-drawer">Open drawer</button>',
        PJXDrawer(
            id="demo-drawer",
            side="right",
            title="Filter results",
            body="<p>Adjust filters to narrow down your results.</p>",
            footer='<button class="pjx-demo-btn" data-pjx-close>Done</button>',
        ).render(),
    ]


def confirm_dialog():
    return [
        """<button class="pjx-demo-btn"
            onclick="pjx.confirm('Delete this file?', { okLabel: 'Delete', danger: true })
                .then(ok => { if (ok) alert('Deleted.') })">Delete file</button>""",
        PJXConfirmDialog(id="demo-confirm").render(),
    ]


def prompt_dialog():
    return [
        """<button class="pjx-demo-btn"
            onclick="pjx.prompt('Rename file', { initial: 'report.pdf', placeholder: 'New name' })
                .then(name => { if (name !== null) alert('Renamed to: ' + name) })">Rename file</button>""",
        PJXPromptDialog(id="demo-prompt").render(),
    ]


def notification():
    return [
        PJXNotification(
            id="demo-notification",
            content="Your changes have been saved.",
            corner="top-right",
            timeout=4000,
        ).render(),
        '<button class="pjx-demo-btn" onclick="pjx.notification.show(\'demo-notification\')">'
        "Show notification</button>",
    ]


def alert():
    return [
        PJXAlert(variant="info", title="Heads up", body="A new version is available.").render(),
        PJXAlert(variant="success", body="Your changes were saved.").render(),
        PJXAlert(variant="warning", body="Your session expires in 5 minutes.").render(),
        PJXAlert(variant="error", body="Could not reach the server.", dismissible=True).render(),
    ]


def tooltip():
    return PJXTooltip(
        id="demo-tooltip",
        trigger="Hover over me",
        tip="This is additional context shown on hover or focus.",
        placement="top",
    ).render()


def popover():
    return PJXPopover(
        id="demo-popover",
        content=(
            PJXPopoverTrigger(id="demo-popover-t", content="Show info", role="dialog").render()
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
    "PJXDrawer": (drawer, 360),
    "PJXConfirmDialog": (confirm_dialog, 360),
    "PJXPromptDialog": (prompt_dialog, 360),
    "PJXNotification": (notification, 140),
    "PJXAlert": (alert, 280),
    "PJXTooltip": (tooltip, 160),
    "PJXPopover": (popover, 200),
}
