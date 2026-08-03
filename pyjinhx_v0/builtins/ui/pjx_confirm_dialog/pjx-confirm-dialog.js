(function () {
    window.pjx = window.pjx || {};
    if (pjx.confirm) return;

    function dialogEl() {
        return document.querySelector('dialog[data-pjx-dialog="confirm"]');
    }

    function confirm(message, options) {
        const opts = options || {};
        const dialog = dialogEl();
        if (!dialog) return Promise.resolve(window.confirm(message));
        if (dialog.open) return Promise.resolve(false); // singleton busy: treat as declined

        const messageEl = dialog.querySelector('.pjx-confirm-dialog__message');
        const okBtn = dialog.querySelector('.pjx-confirm-dialog__ok');
        const cancelBtn = dialog.querySelector('.pjx-confirm-dialog__cancel');
        messageEl.textContent = message;
        okBtn.classList.toggle('pjx-confirm-dialog__ok--danger', Boolean(opts.danger));
        const prevOk = okBtn.textContent;
        const prevCancel = cancelBtn.textContent;
        if (opts.okLabel) okBtn.textContent = opts.okLabel;
        if (opts.cancelLabel) cancelBtn.textContent = opts.cancelLabel;

        dialog.showModal();

        return new Promise((resolve) => {
            const ac = new AbortController();
            const done = (result) => {
                okBtn.textContent = prevOk;
                cancelBtn.textContent = prevCancel;
                ac.abort();
                if (dialog.open) dialog.close();
                resolve(result);
            };
            okBtn.addEventListener('click', () => done(true), { signal: ac.signal });
            cancelBtn.addEventListener('click', () => done(false), { signal: ac.signal });
            // Esc / programmatic close resolves false.
            dialog.addEventListener('close', () => done(false), { signal: ac.signal });
        });
    }

    // Every plain hx-confirm="..." routes through the styled dialog.
    document.addEventListener('htmx:confirm', (evt) => {
        if (!evt.detail.question) return;
        if (!dialogEl()) return; // no singleton mounted: htmx falls back to window.confirm
        evt.preventDefault();
        const elt = evt.detail.elt;
        confirm(evt.detail.question, {
            danger: Boolean(elt && elt.hasAttribute('data-pjx-confirm-danger')),
            okLabel: elt ? elt.getAttribute('data-pjx-confirm-ok') : null,
            cancelLabel: elt ? elt.getAttribute('data-pjx-confirm-cancel') : null,
        }).then((confirmed) => {
            if (confirmed) evt.detail.issueRequest(true);
        });
    });

    // Non-htmx forms: <form data-confirm="...">.
    document.addEventListener('submit', (evt) => {
        if (evt.defaultPrevented) return; // htmx (or other code) already owns this submit
        const question = evt.target.getAttribute && evt.target.getAttribute('data-confirm');
        if (!question || !dialogEl()) return;
        evt.preventDefault();
        confirm(question, {
            danger: evt.target.hasAttribute('data-pjx-confirm-danger'),
            okLabel: evt.target.getAttribute('data-pjx-confirm-ok'),
            cancelLabel: evt.target.getAttribute('data-pjx-confirm-cancel'),
        }).then((confirmed) => {
            if (confirmed) evt.target.submit();
        });
    });

    pjx.confirm = confirm;
}());
