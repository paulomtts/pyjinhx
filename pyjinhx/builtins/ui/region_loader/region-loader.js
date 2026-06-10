(function () {
    window.px = window.px || {};
    px.loader = px.loader || {};
    if (px.loader.region) return;

    const counts = new Map();

    function fire(el, name, detail) {
        el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: false, detail: detail || {},
        }));
    }

    // Only strip classes while a hide is genuinely in progress; a stale
    // animationend (e.g. the fade-in after a cancelled hide) must be a no-op.
    function finishHide(e) {
        if (!e.target.classList.contains('px-region-loader--hiding')) return;
        e.target.classList.remove('px-region-loader--visible', 'px-region-loader--hiding');
        fire(e.target, 'px:region-loader:hide', {});
    }

    function show(id) {
        const overlay = document.getElementById(id);
        if (!overlay) return;
        const count = counts.get(id) || 0;
        counts.set(id, count + 1);
        if (count > 0) return;
        overlay.classList.remove('px-region-loader--hiding');
        overlay.classList.add('px-region-loader--visible');
        fire(overlay, 'px:region-loader:show', {});
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
        overlay.classList.add('px-region-loader--hiding');
        overlay.addEventListener('animationend', finishHide);
    }

    function reset(id) {
        counts.delete(id);
        const overlay = document.getElementById(id);
        if (!overlay) return;
        overlay.classList.remove('px-region-loader--visible', 'px-region-loader--hiding');
    }

    px.loader.region = { show: show, hide: hide, reset: reset };
}());
