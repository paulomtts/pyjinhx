(function () {
    window.px = window.px || {};
    if (px.drawer) return;

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function open(id, reason, trigger) {
        const drawer = document.getElementById(id);
        if (!drawer || drawer.open) return false;
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(drawer, 'px:drawer:before-open', detail, true)) return false;
        drawer.showModal();
        fire(drawer, 'px:drawer:open', detail);
        return true;
    }

    function close(id, reason, trigger) {
        const drawer = document.getElementById(id);
        if (!drawer || !drawer.open) return false;
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(drawer, 'px:drawer:before-close', detail, true)) return false;
        drawer.classList.add('px-drawer--closing');
        drawer.addEventListener('animationend', () => {
            drawer.classList.remove('px-drawer--closing');
            drawer.close();
            fire(drawer, 'px:drawer:close', detail);
            if (drawer.hasAttribute('data-px-remove-on-close')) drawer.remove();
        }, { once: true });
        return true;
    }

    document.addEventListener('click', (e) => {
        const opener = e.target.closest('[data-px-open]');
        if (opener) {
            const target = document.getElementById(opener.getAttribute('data-px-open'));
            if (target && target.classList.contains('px-drawer')) {
                open(target.id, 'trigger', opener);
                return;
            }
        }
        const closer = e.target.closest('[data-px-close]');
        if (closer) {
            const dialog = closer.closest('dialog.px-drawer');
            if (dialog) {
                close(dialog.id, 'trigger', closer);
                return;
            }
        }
        if (e.target.tagName === 'DIALOG' && e.target.classList.contains('px-drawer')) {
            close(e.target.id, 'backdrop', null);
        }
    });

    // Native Escape fires `cancel`; intercept (capture — it doesn't bubble)
    // and route through close() so px:drawer:before-close can veto it.
    document.addEventListener('cancel', (e) => {
        const dialog = e.target;
        if (!(dialog instanceof HTMLDialogElement)) return;
        if (!dialog.classList.contains('px-drawer')) return;
        e.preventDefault();
        close(dialog.id, 'escape', null);
    }, true);

    // open_on_mount: fragment-delivered drawers (hx-swap="beforeend") open on arrival.
    function openMounted(rootNode) {
        if (!rootNode.querySelectorAll) return;
        rootNode.querySelectorAll('dialog.px-drawer[data-px-open-on-mount]').forEach((d) => {
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

    px.drawer = { open: open, close: close };
}());
