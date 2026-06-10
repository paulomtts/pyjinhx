(function () {
    window.px = window.px || {};
    px.loader = px.loader || {};
    if (px.loader.region) return;

    const VISIBLE = 'px-region-loader--visible';
    const HIDING = 'px-region-loader--hiding';
    const counts = new Map();
    const hideTimers = new Map();

    function fire(el, name) {
        el.dispatchEvent(new CustomEvent(name, { bubbles: true, detail: {} }));
    }

    function clearHideTimer(id) {
        clearTimeout(hideTimers.get(id));
        hideTimers.delete(id);
    }

    // Idempotent: runs once per hide via the HIDING guard, whether reached
    // from animationend or the fallback timer. A resurrecting show() strips
    // HIDING first, turning any stale finalize into a no-op.
    function finalizeHide(overlay, id) {
        clearHideTimer(id);
        if (!overlay.classList.contains(HIDING)) return;
        overlay.classList.remove(VISIBLE, HIDING);
        fire(overlay, 'px:region-loader:hide');
    }

    function onAnimationEnd(e) {
        if (!e.target.classList || !e.target.classList.contains(HIDING)) return;
        finalizeHide(e.target, e.target.id);
    }

    function show(id) {
        const overlay = document.getElementById(id);
        if (!overlay) return;
        const count = counts.get(id) || 0;
        counts.set(id, count + 1);
        if (count > 0) return;
        clearHideTimer(id);
        overlay.classList.remove(HIDING);
        const wasVisible = overlay.classList.contains(VISIBLE);
        overlay.classList.add(VISIBLE);
        if (!wasVisible) fire(overlay, 'px:region-loader:show');
    }

    function hide(id) {
        const overlay = document.getElementById(id);
        if (!overlay) {
            // Element gone mid-flight: drop all per-id state so a future
            // mount with the same id starts clean.
            counts.delete(id);
            clearHideTimer(id);
            return;
        }
        const count = counts.get(id) || 0;
        if (count === 0) return;
        if (count > 1) {
            counts.set(id, count - 1);
            return;
        }
        counts.delete(id);
        overlay.classList.add(HIDING);
        // Same-function listeners dedupe, so repeated hides never stack.
        overlay.addEventListener('animationend', onAnimationEnd);
        // Fallback for animation-less environments (prefers-reduced-motion).
        hideTimers.set(id, setTimeout(() => finalizeHide(overlay, id), 250));
    }

    function reset(id) {
        counts.delete(id);
        clearHideTimer(id);
        const overlay = document.getElementById(id);
        if (!overlay) return;
        overlay.classList.remove(VISIBLE, HIDING);
    }

    async function wrap(id, promise) {
        show(id);
        try {
            return await promise;
        } finally {
            hide(id);
        }
    }

    px.loader.region = { show: show, hide: hide, reset: reset, wrap: wrap };
}());
