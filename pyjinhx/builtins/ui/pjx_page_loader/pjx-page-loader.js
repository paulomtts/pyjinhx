(function () {
    window.pjx = window.pjx || {};
    pjx.loader = pjx.loader || {};
    if (pjx.loader.page) return;

    function fire(el, name) {
        el.dispatchEvent(new CustomEvent(name, { bubbles: true, detail: {} }));
    }

    function loaderEl() {
        return document.querySelector('[data-pjx-page-loader]');
    }

    function navTargets() {
        const el = loaderEl();
        if (!el || !el.dataset.navTargets) return new Set();
        return new Set(el.dataset.navTargets.split(',').map((s) => s.trim()).filter(Boolean));
    }

    let pending = 0;

    function show() {
        pending += 1;
        const el = loaderEl();
        if (pending === 1 && el && !el.classList.contains('pjx-page-loader--active')) {
            el.classList.add('pjx-page-loader--active');
            fire(el, 'pjx:page-loader:show');
        }
    }

    function hide() {
        setTimeout(() => {
            pending -= 1;
            if (pending <= 0) {
                pending = 0;
                const el = loaderEl();
                if (el && el.classList.contains('pjx-page-loader--active')) {
                    el.classList.remove('pjx-page-loader--active');
                    fire(el, 'pjx:page-loader:hide');
                }
            }
        }, 300);
    }

    function reset() {
        pending = 0;
        const el = loaderEl();
        if (el) el.classList.remove('pjx-page-loader--active');
    }

    async function wrap(promise) {
        show();
        try {
            return await promise;
        } finally {
            hide();
        }
    }

    function isNavigationRequest(detail) {
        const config = detail && detail.requestConfig;
        const verb = ((config && config.verb) || 'get').toLowerCase();
        if (verb !== 'get') return false;
        const target = detail.target || (config && config.target);
        return Boolean(target && target.id && navTargets().has(target.id));
    }

    function shouldTrack(detail) {
        const elt = detail && detail.elt;
        if (elt && elt.closest && elt.closest('[data-pjx-loader]')) return true;
        return isNavigationRequest(detail);
    }

    document.addEventListener('htmx:beforeRequest', (e) => {
        if (e.defaultPrevented) return; // cancelled request: its xhr is never sent
        if (!shouldTrack(e.detail)) return;
        const xhr = e.detail && e.detail.xhr;
        if (!xhr) return;
        show();
        // loadend is terminal on load/error/abort/timeout — even when htmx
        // discards a superseded response. Same release cue as pjx.js.
        xhr.addEventListener('loadend', () => hide(), { once: true });
    });
    document.addEventListener('htmx:historyRestore', reset);

    // Cold load: the template ships active (active_on_load); hide when ready.
    function coldLoadDone() {
        const el = loaderEl();
        if (el) el.classList.remove('pjx-page-loader--active');
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', coldLoadDone);
    } else {
        coldLoadDone();
    }

    pjx.loader.page = { show: show, hide: hide, wrap: wrap, reset: reset };
}());
