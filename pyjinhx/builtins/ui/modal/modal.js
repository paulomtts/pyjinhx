(function () {
    window.px = window.px || {};
    if (px.modal) return;

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function open(id, reason, trigger) {
        const modal = document.getElementById(id);
        if (!modal || modal.open) return false;
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(modal, 'px:modal:before-open', detail, true)) return false;
        modal.showModal();
        fire(modal, 'px:modal:open', detail);
        return true;
    }

    function close(id, reason, trigger) {
        const modal = document.getElementById(id);
        if (!modal || !modal.open) return false;
        if (modal.classList.contains('px-modal--closing')) return false;
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(modal, 'px:modal:before-close', detail, true)) return false;
        modal.classList.add('px-modal--closing');

        let fallbackTimer = null;
        function finalize() {
            modal.removeEventListener('animationend', onAnimationEnd);
            clearTimeout(fallbackTimer);
            if (!modal.classList.contains('px-modal--closing')) return;
            modal.classList.remove('px-modal--closing');
            modal.close();
            fire(modal, 'px:modal:close', detail);
            if (modal.hasAttribute('data-px-remove-on-close')) modal.remove();
        }
        function onAnimationEnd(e) {
            if (e.target !== modal) return; // ignore bubbled descendant animations
            finalize();
        }
        modal.addEventListener('animationend', onAnimationEnd);
        // Fallback for animation-less environments (prefers-reduced-motion, overrides).
        fallbackTimer = setTimeout(finalize, 250);
        return true;
    }

    document.addEventListener('click', (e) => {
        const opener = e.target.closest('[data-px-open]');
        if (opener) {
            const target = document.getElementById(opener.getAttribute('data-px-open'));
            if (target && target.classList.contains('px-modal')) {
                open(target.id, 'trigger', opener);
                return;
            }
        }
        const closer = e.target.closest('[data-px-close]');
        if (closer) {
            const dialog = closer.closest('dialog.px-modal');
            if (dialog) {
                close(dialog.id, 'trigger', closer);
                return;
            }
        }
        if (e.target.tagName === 'DIALOG' && e.target.classList.contains('px-modal')) {
            close(e.target.id, 'backdrop', null);
        }
    });

    // Native Escape fires `cancel`; intercept (capture — it doesn't bubble)
    // and route through close() so px:modal:before-close can veto it.
    document.addEventListener('cancel', (e) => {
        const dialog = e.target;
        if (!(dialog instanceof HTMLDialogElement)) return;
        if (!dialog.classList.contains('px-modal')) return;
        e.preventDefault();
        close(dialog.id, 'escape', null);
    }, true);

    // open_on_mount: fragment-delivered modals (hx-swap="beforeend") open on arrival.
    function openMounted(rootNode) {
        if (rootNode.matches && rootNode.matches('dialog.px-modal[data-px-open-on-mount]')) {
            if (!rootNode.open) open(rootNode.id, 'api', null);
        }
        if (!rootNode.querySelectorAll) return;
        rootNode.querySelectorAll('dialog.px-modal[data-px-open-on-mount]').forEach((m) => {
            if (!m.open) open(m.id, 'api', null);
        });
    }
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((m) => m.addedNodes.forEach((n) => {
            if (n.nodeType === 1) openMounted(n);
        }));
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => openMounted(document));
    } else {
        openMounted(document);
    }

    px.modal = { open: open, close: close };
}());
