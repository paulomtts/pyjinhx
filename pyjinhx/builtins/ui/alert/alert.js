(function () {
    window.px = window.px || {};
    if (px._alertWired) return;
    px._alertWired = true;

    const DISMISSIBLE = '.px-notification, .px-alert, dialog.px-modal, dialog.px-drawer, [data-px-popover-panel]';

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    document.addEventListener('click', (e) => {
        const closer = e.target.closest('[data-px-close]');
        if (!closer) return;
        const dismissible = closer.closest(DISMISSIBLE);
        if (!dismissible || !dismissible.classList.contains('px-alert')) return;
        const detail = { reason: 'trigger', trigger: closer };
        if (!fire(dismissible, 'px:alert:before-dismiss', detail, true)) return;
        dismissible.classList.add('px-alert--dismissed');
        fire(dismissible, 'px:alert:dismiss', detail);
    });
}());
