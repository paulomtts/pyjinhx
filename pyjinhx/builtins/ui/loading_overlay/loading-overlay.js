(function () {
    window.px = window.px || {};
    if (px.overlay) return;

    const counts = new Map();

    function fire(el, name, detail) {
        el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: false, detail: detail || {},
        }));
    }

    // Only strip classes while a hide is genuinely in progress; a stale
    // animationend (e.g. the fade-in after a cancelled hide) must be a no-op.
    function finishHide(e) {
        if (!e.target.classList.contains('px-loading-overlay--hiding')) return;
        e.target.classList.remove('px-loading-overlay--visible', 'px-loading-overlay--hiding');
        fire(e.target, 'px:overlay:hide', {});
    }

    function show(id) {
        const overlay = document.getElementById(id);
        if (!overlay) return;
        const count = counts.get(id) || 0;
        counts.set(id, count + 1);
        if (count > 0) return;
        overlay.classList.remove('px-loading-overlay--hiding');
        overlay.classList.add('px-loading-overlay--visible');
        fire(overlay, 'px:overlay:show', {});
    }

    function hide(id) {
        const overlay = document.getElementById(id);
        if (!overlay) return;
        const count = counts.get(id) || 0;
        if (count === 0) return;
        if (count > 1) {
            counts.set(id, count - 1);
            return;
        }
        counts.delete(id);
        overlay.classList.add('px-loading-overlay--hiding');
        overlay.addEventListener('animationend', finishHide);
    }

    function reset(id) {
        counts.delete(id);
        const overlay = document.getElementById(id);
        if (!overlay) return;
        overlay.classList.remove('px-loading-overlay--visible', 'px-loading-overlay--hiding');
    }

    px.overlay = { show: show, hide: hide, reset: reset };
}());
