(function () {
    window.pjx = window.pjx || {};
    if (pjx.lazyLoad) return;

    var ERROR_CLASS = 'pjx-lazy-load--error';

    // Replace the placeholder of a lazy region whose own request failed
    // terminally. htmx never swaps on a non-2xx/timeout/network error, so the
    // placeholder (skeleton/spinner) would otherwise read "loading…" forever.
    function showError(el) {
        if (el.classList.contains(ERROR_CLASS)) return; // already replaced
        var tpl = el.querySelector(':scope > template[data-pjx-lazy-error]');
        el.classList.add(ERROR_CLASS);
        if (tpl && tpl.innerHTML.trim()) {
            el.innerHTML = tpl.innerHTML; // author-supplied error markup
            return;
        }
        var box = document.createElement('div');
        box.className = 'pjx-lazy-load__error';
        box.setAttribute('role', 'alert');
        box.textContent = el.getAttribute('data-pjx-error-text') || 'Failed to load.';
        el.replaceChildren(box);
    }

    // afterRequest fires for every terminal outcome (success, error, abort,
    // timeout); detail.successful is false on the failures we care about.
    document.addEventListener('htmx:afterRequest', function (e) {
        var d = e.detail;
        if (!d || d.successful) return;
        var el = d.elt && d.elt.closest && d.elt.closest('[data-pjx-lazy-load]');
        // Only the lazy element's OWN request — not a failure bubbling up from
        // content already swapped into it.
        if (!el || d.elt !== el) return;
        showError(el);
    });

    pjx.lazyLoad = { showError: showError };
}());
