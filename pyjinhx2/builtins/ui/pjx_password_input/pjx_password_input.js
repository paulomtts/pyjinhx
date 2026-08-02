(function () {
    window.pjx = window.pjx || {};
    if (pjx._passwordWired) return;
    pjx._passwordWired = true;

    document.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-pjx-password-toggle]');
        if (!btn) return;

        const root = btn.closest('[data-pjx-password]');
        if (!root) return;

        const field = root.querySelector('.pjx-password-input__field');
        if (!field) return;

        const isShowing = field.type === 'text';
        field.type = isShowing ? 'password' : 'text';

        // single ARIA signal: static label + aria-pressed (ARIA APG toggle-button pattern)
        btn.setAttribute('aria-pressed', String(!isShowing));
        btn.classList.toggle('pjx-password-input__toggle--on', !isShowing);
    });
}());
