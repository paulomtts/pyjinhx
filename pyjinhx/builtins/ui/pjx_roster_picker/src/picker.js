(function () {
    window.pjx = window.pjx || {};
    // The namespace is the guard: a second copy of the script (an htmx swap
    // re-running it, or two pickers shipping it) finds it and returns before
    // binding, so the document listeners below exist once per page.
    if (window.pjx.rosterPicker) return;
    window.pjx.rosterPicker = {};

    function pickerOf(el) {
        return el.closest('[data-pjx-roster-picker]');
    }

    // Null for a disabled picker, which renders no search box.
    function searchInput(picker) {
        return picker.querySelector('.pjx-roster-picker__input');
    }

    function resultsMount(picker) {
        return picker.querySelector('.pjx-roster-picker__results');
    }

    function isOpen(input) {
        return input.getAttribute('aria-expanded') === 'true';
    }

    // Every open and close goes through here, so the input's aria-expanded
    // and the mount's hidden never disagree. Closing only hides the rows.
    function setOpen(picker, open) {
        const input = searchInput(picker);
        if (!input) return;
        input.setAttribute('aria-expanded', open ? 'true' : 'false');
        resultsMount(picker).hidden = !open;
    }

    // The input's hx-trigger turns roster-picker-open into a debounced search
    // for whatever the box already holds.
    function openByUser(input) {
        const picker = pickerOf(input);
        if (!picker || input.disabled || isOpen(input)) return;
        setOpen(picker, true);
        input.dispatchEvent(new Event('roster-picker-open'));
    }

    // An event can target document itself, which has no closest or matches.
    function isSearchInput(target) {
        return target instanceof Element && target.matches('.pjx-roster-picker__input');
    }

    document.addEventListener('focusin', function (event) {
        if (isSearchInput(event.target)) openByUser(event.target);
    });
})();
