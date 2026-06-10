(function () {
    window.px = window.px || {};
    if (px.prompt) return;

    function dialogEl() {
        return document.querySelector('dialog[data-px-dialog="prompt"]');
    }

    function prompt(title, options) {
        const opts = options || {};
        const dialog = dialogEl();
        if (!dialog) return Promise.resolve(window.prompt(title, opts.initial || ''));

        const label = dialog.querySelector('.px-prompt-dialog__label');
        const input = dialog.querySelector('.px-prompt-dialog__input');
        const okBtn = dialog.querySelector('.px-prompt-dialog__ok');
        const cancelBtn = dialog.querySelector('.px-prompt-dialog__cancel');
        const form = dialog.querySelector('form');

        label.textContent = title;
        input.value = opts.initial || '';
        input.placeholder = opts.placeholder || '';
        const prevOk = okBtn.textContent;
        const prevCancel = cancelBtn.textContent;
        if (opts.okLabel) okBtn.textContent = opts.okLabel;
        if (opts.cancelLabel) cancelBtn.textContent = opts.cancelLabel;

        dialog.showModal();
        // Defer focus so the dialog has rendered; select() lets the user
        // type-replace a prefilled value immediately.
        setTimeout(() => { input.focus(); input.select(); }, 0);

        return new Promise((resolve) => {
            const ac = new AbortController();
            const done = (result) => {
                okBtn.textContent = prevOk;
                cancelBtn.textContent = prevCancel;
                if (dialog.open) dialog.close();
                ac.abort();
                resolve(result);
            };
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                done(input.value.trim() || null);
            }, { signal: ac.signal });
            cancelBtn.addEventListener('click', () => done(null), { signal: ac.signal });
            dialog.addEventListener('close', () => done(null), { signal: ac.signal });
        });
    }

    px.prompt = prompt;
}());
