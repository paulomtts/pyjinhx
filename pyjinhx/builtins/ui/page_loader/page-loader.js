(function () {
    window.px = window.px || {};
    if (px.loader) return;

    function fire(el, name) {
        el.dispatchEvent(new CustomEvent(name, { bubbles: true, detail: {} }));
    }

    function loaderEl() {
        return document.querySelector('[data-px-page-loader]');
    }

    function navTargets() {
        const el = loaderEl();
        if (!el || !el.dataset.navTargets) return new Set();
        return new Set(el.dataset.navTargets.split(',').map((s) => s.trim()).filter(Boolean));
    }

    let pending = 0;
    const tracked = new WeakSet();

    function show() {
        pending += 1;
        const el = loaderEl();
        if (pending === 1 && el && !el.classList.contains('px-page-loader--active')) {
            el.classList.add('px-page-loader--active');
            fire(el, 'px:loader:show');
        }
    }

    function hide() {
        setTimeout(() => {
            pending -= 1;
            if (pending <= 0) {
                pending = 0;
                const el = loaderEl();
                if (el && el.classList.contains('px-page-loader--active')) {
                    el.classList.remove('px-page-loader--active');
                    fire(el, 'px:loader:hide');
                }
            }
        }, 300);
    }

    function reset() {
        pending = 0;
        const el = loaderEl();
        if (el) el.classList.remove('px-page-loader--active');
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
        if (elt && elt.closest && elt.closest('[data-px-loader]')) return true;
        return isNavigationRequest(detail);
    }

    document.addEventListener('htmx:beforeRequest', (e) => {
        if (!shouldTrack(e.detail)) return;
        tracked.add(e.detail);
        show();
    });
    ['htmx:afterRequest', 'htmx:responseError', 'htmx:sendError'].forEach((name) => {
        document.addEventListener(name, (e) => {
            if (!tracked.has(e.detail)) return;
            tracked.delete(e.detail);
            hide();
        });
    });
    document.addEventListener('htmx:historyRestore', reset);

    // Cold load: the template ships active (active_on_load); hide when ready.
    function coldLoadDone() {
        const el = loaderEl();
        if (el) el.classList.remove('px-page-loader--active');
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', coldLoadDone);
    } else {
        coldLoadDone();
    }

    px.loader = { show: show, hide: hide, wrap: wrap, reset: reset };
}());
