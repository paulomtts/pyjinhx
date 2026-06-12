(function () {
    window.pjx = window.pjx || {};
    if (pjx.drawer) return;  // Note: pjx namespace is shared; drawer function under pjx.drawer

    const DISMISSIBLE = '.pjx-notification, .pjx-alert, dialog.pjx-modal, dialog.pjx-drawer, [data-pjx-popover-panel]';

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function open(id, reason, trigger) {
        const drawer = document.getElementById(id);
        if (!drawer || drawer.open) return false;
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(drawer, 'pjx:drawer:before-open', detail, true)) return false;
        drawer.showModal();
        fire(drawer, 'pjx:drawer:open', detail);
        return true;
    }

    function close(id, reason, trigger) {
        const drawer = document.getElementById(id);
        if (!drawer || !drawer.open) return false;
        if (drawer.classList.contains('pjx-drawer--closing')) return false;
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(drawer, 'pjx:drawer:before-close', detail, true)) return false;
        drawer.classList.add('pjx-drawer--closing');

        let fallbackTimer = null;
        function finalize() {
            drawer.removeEventListener('animationend', onAnimationEnd);
            clearTimeout(fallbackTimer);
            if (!drawer.classList.contains('pjx-drawer--closing')) return;
            drawer.classList.remove('pjx-drawer--closing');
            drawer.close();
            fire(drawer, 'pjx:drawer:close', detail);
            if (drawer.hasAttribute('data-pjx-remove-on-close')) drawer.remove();
        }
        function onAnimationEnd(e) {
            if (e.target !== drawer) return; // ignore bubbled descendant animations
            finalize();
        }
        drawer.addEventListener('animationend', onAnimationEnd);
        // Fallback for animation-less environments (prefers-reduced-motion, overrides).
        fallbackTimer = setTimeout(finalize, 250);
        return true;
    }

    document.addEventListener('click', (e) => {
        const opener = e.target.closest('[data-pjx-open]');
        if (opener) {
            const target = document.getElementById(opener.getAttribute('data-pjx-open'));
            if (target && target.classList.contains('pjx-drawer')) {
                open(target.id, 'trigger', opener);
                return;
            }
        }
        const closer = e.target.closest('[data-pjx-close]');
        if (closer) {
            const dismissible = closer.closest(DISMISSIBLE);
            if (dismissible && dismissible.matches('dialog.pjx-drawer')) {
                close(dismissible.id, 'trigger', closer);
            }
            return;
        }
        if (e.target.tagName === 'DIALOG' && e.target.classList.contains('pjx-drawer')) {
            close(e.target.id, 'backdrop', null);
        }
    });

    // Native Escape fires `cancel`; intercept (capture — it doesn't bubble)
    // and route through close() so pjx:drawer:before-close can veto it.
    document.addEventListener('cancel', (e) => {
        const dialog = e.target;
        if (!(dialog instanceof HTMLDialogElement)) return;
        if (!dialog.classList.contains('pjx-drawer')) return;
        e.preventDefault();
        close(dialog.id, 'escape', null);
    }, true);

    // open_on_mount: fragment-delivered drawers (hx-swap="beforeend") open on arrival.
    function openMounted(rootNode) {
        if (rootNode.matches && rootNode.matches('dialog.pjx-drawer[data-pjx-open-on-mount]')) {
            if (!rootNode.open) open(rootNode.id, 'api', null);
        }
        if (!rootNode.querySelectorAll) return;
        rootNode.querySelectorAll('dialog.pjx-drawer[data-pjx-open-on-mount]').forEach((d) => {
            if (!d.open) open(d.id, 'api', null);
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

    pjx.drawer = { open: open, close: close };  // pjx.drawer namespace (pjx prefix is shared; drawer is component-specific)
}());
