(function () {
    window.px = window.px || {};
    if (px.notification) return;

    const DISMISSIBLE = '.px-notification, .px-alert, dialog.px-modal, dialog.px-drawer, [data-px-popover-panel]';
    const timers = new Map();

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function show(id, reason) {
        const el = document.getElementById(id);
        if (!el || el.classList.contains('px-notification--visible')) return false;
        const detail = { reason: reason || 'api', trigger: null };
        if (!fire(el, 'px:notification:before-show', detail, true)) return false;
        el.classList.remove('px-notification--hiding');
        el.classList.add('px-notification--visible');
        fire(el, 'px:notification:show', detail);

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
        if (!el.classList.contains('px-notification--visible')) return false;
        if (el.classList.contains('px-notification--hiding')) return false;
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(el, 'px:notification:before-hide', detail, true)) return false;
        clearTimeout(timers.get(id));
        timers.delete(id);
        el.classList.add('px-notification--hiding');

        let fallbackTimer = null;
        function finalize() {
            el.removeEventListener('animationend', onAnimationEnd);
            clearTimeout(fallbackTimer);
            if (!el.classList.contains('px-notification--hiding')) return;
            el.classList.remove('px-notification--visible', 'px-notification--hiding');
            fire(el, 'px:notification:hide', detail);
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
        const closer = e.target.closest('[data-px-close]');
        if (!closer) return;
        const dismissible = closer.closest(DISMISSIBLE);
        if (dismissible && dismissible.classList.contains('px-notification')) {
            hide(dismissible.id, 'trigger', closer);
        }
    });

    function showMounted(rootNode) {
        if (rootNode.matches && rootNode.matches('.px-notification[data-px-autoshow]')) {
            show(rootNode.id, 'api');
        }
        if (!rootNode.querySelectorAll) return;
        rootNode.querySelectorAll('.px-notification[data-px-autoshow]').forEach((n) => {
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

    px.notification = { show: show, hide: hide };
}());
