(function () {
    window.pjx = window.pjx || {};
    if (pjx._alertWired) return;
    pjx._alertWired = true;

    const DISMISSIBLE = '.pjx-notification, .pjx-alert, dialog.pjx-modal, dialog.pjx-drawer, [data-pjx-popover-panel]';

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    document.addEventListener('click', (e) => {
        const closer = e.target.closest('[data-pjx-close]');
        if (!closer) return;
        const dismissible = closer.closest(DISMISSIBLE);
        if (!dismissible || !dismissible.classList.contains('pjx-alert')) return;
        const detail = { reason: 'trigger', trigger: closer };
        if (!fire(dismissible, 'pjx:alert:before-dismiss', detail, true)) return;
        dismissible.classList.add('pjx-alert--dismissed');
        fire(dismissible, 'pjx:alert:dismiss', detail);
    });
}());
