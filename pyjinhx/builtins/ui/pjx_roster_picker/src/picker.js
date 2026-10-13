(function () {
    window.pjx = window.pjx || {};
    // A second copy of the script (an htmx swap re-running it, or two pickers
    // shipping it twice) must keep the namespace the first copy set up.
    if (window.pjx.rosterPicker) return;
    window.pjx.rosterPicker = {};
})();
