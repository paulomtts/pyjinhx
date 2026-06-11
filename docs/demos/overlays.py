from pyjinhx.builtins import (
    Alert,
    ConfirmDialog,
    Drawer,
    Modal,
    Notification,
    Popover,
    PopoverPanel,
    PopoverTrigger,
    PromptDialog,
    Tooltip,
)


def modal():
    return [
        '<button class="px-demo-btn" data-px-open="demo-modal">Open modal</button>',
        Modal(
            id="demo-modal",
            title="Confirm changes",
            body="Your draft will be published immediately. This action cannot be undone.",
            footer='<button class="px-demo-btn" data-px-close>Cancel</button>',
        ).render(),
    ]


def drawer():
    return [
        '<button class="px-demo-btn" data-px-open="demo-drawer">Open drawer</button>',
        Drawer(
            id="demo-drawer",
            side="right",
            title="Filter results",
            body="<p>Adjust filters to narrow down your results.</p>",
            footer='<button class="px-demo-btn" data-px-close>Done</button>',
        ).render(),
    ]


def confirm_dialog():
    return [
        """<button class="px-demo-btn"
            onclick="px.confirm('Delete this file?', { okLabel: 'Delete', danger: true })
                .then(ok => { if (ok) alert('Deleted.') })">Delete file</button>""",
        ConfirmDialog(id="demo-confirm").render(),
    ]


def prompt_dialog():
    return [
        """<button class="px-demo-btn"
            onclick="px.prompt('Rename file', { initial: 'report.pdf', placeholder: 'New name' })
                .then(name => { if (name !== null) alert('Renamed to: ' + name) })">Rename file</button>""",
        PromptDialog(id="demo-prompt").render(),
    ]


def notification():
    return Notification(
        id="demo-notification",
        content="Your changes have been saved.",
        corner="top-right",
        timeout=4000,
        autoshow=True,
    ).render()


def alert():
    return Alert(
        id="demo-alert",
        variant="warning",
        title="Storage almost full",
        body="You have used 90% of your storage quota. Consider removing old files.",
        dismissible=True,
    ).render()


def tooltip():
    return Tooltip(
        id="demo-tooltip",
        trigger="Hover over me",
        tip="This is additional context shown on hover or focus.",
        placement="top",
    ).render()


def popover():
    return Popover(
        id="demo-popover",
        content=(
            PopoverTrigger(id="demo-popover-t", content="Show info", role="dialog").render()
            + PopoverPanel(
                id="demo-popover-p",
                role="dialog",
                content="<p>Here is some extra detail about this item.</p>",
            ).render()
        ),
    ).render()


DEMOS = {
    "Modal": (modal, 520),
    "Drawer": (drawer, 360),
    "ConfirmDialog": (confirm_dialog, 360),
    "PromptDialog": (prompt_dialog, 360),
    "Notification": (notification, 160),
    "Alert": (alert, 160),
    "Tooltip": (tooltip, 160),
    "Popover": (popover, 200),
}
