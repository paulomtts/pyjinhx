(function () {
    window.pjx = window.pjx || {};
    if (pjx._accordionWired) return;
    pjx._accordionWired = true;

    // Stop clicks inside .pjx-accordion__actions from toggling the native
    // details element. The summary's toggle is the click's *default action*,
    // so preventDefault() in the capture phase cancels it before the browser
    // acts. We deliberately do NOT stopPropagation(), so the action element's
    // own htmx/Alpine/click handlers (which run in the bubble phase) still fire.
    document.addEventListener('click', function (e) {
        var actions = e.target.closest('.pjx-accordion__actions');
        if (!actions) return;
        e.preventDefault();
    }, true); // capture phase: runs before the summary's default toggle

    // aria-disabled doesn't stop a <summary>'s native toggle; cancel it too.
    document.addEventListener('click', function (e) {
        var trigger = e.target.closest('.pjx-accordion__trigger[aria-disabled="true"]');
        if (!trigger) return;
        e.preventDefault();
    }, true);
})();
