(function () {
    window.pjx = window.pjx || {};
    pjx.loader = pjx.loader || {};
    if (pjx.loader.region) return;

    const VISIBLE = 'pjx-region-loader--visible';
    const HIDING = 'pjx-region-loader--hiding';
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
        fire(overlay, 'pjx:region-loader:hide');
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
        const isFresh = !overlay.classList.contains(VISIBLE) && !overlay.classList.contains(HIDING);
        if (count > 0 && !isFresh) return;
        clearHideTimer(id);
        overlay.classList.remove(HIDING);
        const wasVisible = overlay.classList.contains(VISIBLE);
        overlay.classList.add(VISIBLE);
        if (!wasVisible) fire(overlay, 'pjx:region-loader:show');
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
        if (!overlay.classList.contains(VISIBLE)) {
            // Same-id node replaced mid-flight: it never showed, so there is
            // no visibility transition to animate or announce.
            clearHideTimer(id);
            return;
        }
        overlay.classList.add(HIDING);
        // Same-function listeners dedupe, so repeated hides never stack.
        overlay.addEventListener('animationend', onAnimationEnd);
        // Fallback for animation-less environments (prefers-reduced-motion).
        // 250ms > the 150ms default out-animation; raw-CSS themes with longer fades get cut to display:none early.
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

    // A swap can replace the overlay's node while sources are still active
    // (count > 0). Re-light replacements after htmx settles — same strategy
    // as the reactive runtime's pjxReapplyLoading. Silent on purpose: the
    // show event for this loading episode already fired on the old node.
    function relight() {
        counts.forEach(function (count, id) {
            if (count <= 0) return;
            const overlay = document.getElementById(id);
            if (!overlay) return;
            if (overlay.classList.contains(VISIBLE) || overlay.classList.contains(HIDING)) return;
            overlay.classList.add(VISIBLE);
        });
    }
    if (document.body) {
        document.body.addEventListener('htmx:afterSettle', relight);
    } else {
        document.addEventListener('DOMContentLoaded', function () {
            document.body.addEventListener('htmx:afterSettle', relight);
        });
    }

    pjx.loader.region = { show: show, hide: hide, reset: reset, wrap: wrap };
}());
