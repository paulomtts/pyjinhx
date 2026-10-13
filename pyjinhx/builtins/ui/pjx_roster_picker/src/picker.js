(function () {
    window.pjx = window.pjx || {};
    // The namespace is the guard: a second copy of the script (an htmx swap
    // re-running it, or two pickers shipping it) finds it and returns before
    // binding, so the document listeners below exist once per page.
    if (window.pjx.rosterPicker) return;
    window.pjx.rosterPicker = {};

    // Focus this script moves (Escape handing it back to the box) is not the
    // user arriving, so it must not reopen the list. focus() dispatches
    // focusin synchronously, so the mark only has to outlive that call.
    let quietInput = null;

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

    function quietFocus(input) {
        quietInput = input;
        try {
            input.focus();
        } finally {
            quietInput = null;
        }
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
        if (isSearchInput(event.target) && event.target !== quietInput) {
            openByUser(event.target);
        }
    });

    // A box that already has focus fires no focusin, so after Escape only the
    // click itself can reopen it. The click that just focused a box finds it
    // open already and does nothing.
    document.addEventListener('click', function (event) {
        if (isSearchInput(event.target)) openByUser(event.target);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape' || !(event.target instanceof Element)) return;
        const search = event.target.closest('.pjx-roster-picker__search');
        const picker = search && pickerOf(search);
        const input = picker && searchInput(picker);
        // A closed list leaves Escape alone, so the next press reaches an
        // enclosing dialog and closes that instead.
        if (!input || !isOpen(input)) return;
        event.preventDefault();
        // Stopped here so a window or dialog listener never sees the press
        // that only closed the list.
        event.stopPropagation();
        setOpen(picker, false);
        // A row focused inside the now-hidden list would strand the keyboard.
        if (event.target !== input) quietFocus(input);
    });
})();
