(function () {
    window.px = window.px || {};
    if (px._passwordWired) return;
    px._passwordWired = true;

    document.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-px-password-toggle]');
        if (!btn) return;

        const root = btn.closest('[data-px-password]');
        if (!root) return;

        const field = root.querySelector('.px-password-input__field');
        if (!field) return;

        const isShowing = field.type === 'text';
        field.type = isShowing ? 'password' : 'text';

        const newLabel = isShowing
            ? btn.dataset.showLabel
            : btn.dataset.hideLabel;
        btn.setAttribute('aria-label', newLabel);
        btn.setAttribute('aria-pressed', String(!isShowing));
        btn.classList.toggle('px-password-input__toggle--on', !isShowing);
    });
}());
