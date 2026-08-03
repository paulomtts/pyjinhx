(function () {
    window.pjx = window.pjx || {};
    if (pjx.notification) return;

    const DISMISSIBLE = '.pjx-notification, .pjx-alert, dialog.pjx-modal, dialog.pjx-drawer, [data-pjx-popover-panel]';
    const timers = new Map();

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function show(id, reason) {
        const el = document.getElementById(id);
        if (!el || el.classList.contains('pjx-notification--visible')) return false;
        const detail = { reason: reason || 'api', trigger: null };
        if (!fire(el, 'pjx:notification:before-show', detail, true)) return false;
        el.classList.remove('pjx-notification--hiding');
        el.classList.add('pjx-notification--visible');
        fire(el, 'pjx:notification:show', detail);

        clearTimeout(timers.get(id));
        const timeout = parseInt(el.dataset.timeout, 10);
        if (timeout > 0) {
            timers.set(id, setTimeout(() => hide(id, 'api'), timeout));
        }
        return true;
    }

    function hide(id, reason, trigger) {
        const el = document.getElementById(id);
        if (!el) {
            clearTimeout(timers.get(id));
            timers.delete(id);
            return false;
        }
        if (!el.classList.contains('pjx-notification--visible')) return false;
        if (el.classList.contains('pjx-notification--hiding')) return false;
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(el, 'pjx:notification:before-hide', detail, true)) return false;
        clearTimeout(timers.get(id));
        timers.delete(id);
        el.classList.add('pjx-notification--hiding');

        let fallbackTimer = null;
        function finalize() {
            el.removeEventListener('animationend', onAnimationEnd);
            clearTimeout(fallbackTimer);
            if (!el.classList.contains('pjx-notification--hiding')) return;
            el.classList.remove('pjx-notification--visible', 'pjx-notification--hiding');
            fire(el, 'pjx:notification:hide', detail);
        }
        function onAnimationEnd(e) {
            if (e.target !== el) return;
            finalize();
        }
        el.addEventListener('animationend', onAnimationEnd);
        fallbackTimer = setTimeout(finalize, 250);
        return true;
    }

    document.addEventListener('click', (e) => {
        const closer = e.target.closest('[data-pjx-close]');
        if (!closer) return;
        const dismissible = closer.closest(DISMISSIBLE);
        if (dismissible && dismissible.classList.contains('pjx-notification')) {
            hide(dismissible.id, 'trigger', closer);
        }
    });

    function showMounted(rootNode) {
        if (rootNode.matches && rootNode.matches('.pjx-notification[data-pjx-autoshow]')) {
            show(rootNode.id, 'api');
        }
        if (!rootNode.querySelectorAll) return;
        rootNode.querySelectorAll('.pjx-notification[data-pjx-autoshow]').forEach((n) => {
            show(n.id, 'api');
        });
    }
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((m) => m.addedNodes.forEach((node) => {
            if (node.nodeType === 1) showMounted(node);
        }));
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => showMounted(document));
    } else {
        showMounted(document);
    }

    pjx.notification = { show: show, hide: hide };
}());
