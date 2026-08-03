(function () {
    window.pjx = window.pjx || {};
    if (pjx.toast) return;

    const wiredEvents = new Set();

    function fire(el, name, detail) {
        el.dispatchEvent(new CustomEvent(name, { bubbles: true, detail: detail || {} }));
    }

    function host() {
        return document.querySelector('[data-pjx-toast-host]');
    }

    function removeToast(hostEl, toast) {
        if (!toast.isConnected) return;
        toast.classList.add('pjx-toast--hiding');
        toast.addEventListener('animationend', () => {
            if (!toast.isConnected) return;
            toast.remove();
            fire(hostEl, 'pjx:toasthost:hide', {});
        }, { once: true });
        // Fallback for animation-less environments.
        setTimeout(() => {
            if (toast.isConnected) {
                toast.remove();
                fire(hostEl, 'pjx:toasthost:hide', {});
            }
        }, 600);
    }

    function showToast(detail) {
        const hostEl = host();
        if (!hostEl) return;
        const data = typeof detail === 'string' ? { message: detail } : (detail || {});
        const level = data.level || 'info';
        const toast = document.createElement('div');
        toast.className = 'pjx-toast pjx-toast--' + level;
        const message = document.createElement('span');
        message.className = 'pjx-toast__message';
        message.textContent = data.message || data.value || '';
        const dismiss = document.createElement('button');
        dismiss.type = 'button';
        dismiss.className = 'pjx-toast__dismiss';
        dismiss.setAttribute('aria-label', hostEl.dataset.dismissLabel || 'Dismiss');
        dismiss.textContent = '✕';
        dismiss.addEventListener('click', () => removeToast(hostEl, toast));
        toast.appendChild(message);
        toast.appendChild(dismiss);
        hostEl.appendChild(toast);
        fire(hostEl, 'pjx:toasthost:show', { level: level });

        const timeout = Number(data.timeout != null ? data.timeout : hostEl.dataset.timeout) || 0;
        if (timeout > 0) setTimeout(() => removeToast(hostEl, toast), timeout);
    }

    function wire(eventName) {
        if (!eventName || wiredEvents.has(eventName)) return;
        wiredEvents.add(eventName);
        // htmx fires HX-Trigger events on the triggering element or body; they
        // bubble to window. Listening on window catches htmx and manual fires.
        window.addEventListener(eventName, (e) => showToast(e.detail));
    }

    function wireMounted(rootNode) {
        if (rootNode.matches && rootNode.matches('[data-pjx-toast-host]')) {
            wire(rootNode.dataset.eventName || 'pjx:toast');
        }
        if (!rootNode.querySelectorAll) return;
        rootNode.querySelectorAll('[data-pjx-toast-host]').forEach((h) => {
            wire(h.dataset.eventName || 'pjx:toast');
        });
    }
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((m) => m.addedNodes.forEach((n) => {
            if (n.nodeType === 1) wireMounted(n);
        }));
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => wireMounted(document));
    } else {
        wireMounted(document);
    }

    pjx.toast = function (message, options) {
        const opts = options || {};
        showToast({ message: message, level: opts.level, timeout: opts.timeout });
    };
}());
