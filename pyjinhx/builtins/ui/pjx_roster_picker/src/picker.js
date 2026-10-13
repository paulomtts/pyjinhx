(function () {
    window.pjx = window.pjx || {};
    // The namespace is the guard: a second copy of the script (an htmx swap
    // re-running it, or two pickers shipping it) finds it and returns before
    // binding, so the document listeners below exist once per page.
    if (window.pjx.rosterPicker) return;
    window.pjx.rosterPicker = {};

    // Focus this script moves (Escape, a pick or a remove handing it back to
    // the box) is not the user arriving, so it must not reopen the list.
    // focus() dispatches focusin synchronously, so the mark only has to
    // outlive that call.
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

    // Only each chip's own hidden input: an app's control nested in a chip's
    // slot can share the class, and template chips are not live DOM.
    function chippedValues(picker) {
        const inputs = picker.querySelectorAll(
            '.pjx-roster-picker__chips > [data-pjx-roster-chip] > .pjx-roster-picker__chip-input'
        );
        return Array.from(inputs, (input) => input.value);
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

    // A row is hidden exactly while its value is chipped, whether or not the
    // route honoured exclude.
    function syncRows(picker) {
        const chipped = chippedValues(picker);
        picker.querySelectorAll('[data-pjx-roster-pick]').forEach((row) => {
            row.hidden = chipped.includes(row.dataset.value);
        });
    }

    // Read after the DOM change, so listeners see the selection as it now is.
    function announceChange(picker) {
        picker.dispatchEvent(
            new CustomEvent('pjx:roster-picker:change', {
                bubbles: true,
                detail: { values: chippedValues(picker) },
            })
        );
    }

    function pickRow(picker, row) {
        if (chippedValues(picker).includes(row.dataset.value)) return;
        const template = row.nextElementSibling;
        const source =
            template instanceof HTMLTemplateElement &&
            template.content.querySelector('[data-pjx-roster-chip]');
        // A stale or hand-built row without its chip has nothing to add.
        if (!source) return;
        const chip = document.importNode(source, true);
        chip.querySelector(':scope > .pjx-roster-picker__chip-input').name = picker.dataset.name;
        const chips = picker.querySelector('.pjx-roster-picker__chips');
        // A single-item picker swaps its one chip rather than refusing.
        if (picker.dataset.maxItems === '1') chips.replaceChildren(chip);
        else chips.append(chip);
        syncRows(picker);
        setOpen(picker, false);
        const input = searchInput(picker);
        if (input) {
            input.value = '';
            quietFocus(input);
        }
        announceChange(picker);
    }

    // Only the mount's live rows: template content is not searched.
    function isListed(picker, value) {
        const rows = resultsMount(picker).querySelectorAll('[data-pjx-roster-pick]');
        return Array.from(rows).some((row) => row.dataset.value === value);
    }

    function removeChip(picker, chip) {
        const value = chip.querySelector(':scope > .pjx-roster-picker__chip-input').value;
        const next = chip.nextElementSibling;
        chip.remove();
        syncRows(picker);
        const input = searchInput(picker);
        // The kept rows were fetched with this value excluded, so a route that
        // honoured exclude left it out; only a fresh search can bring it back.
        if (input && !isListed(picker, value)) input.removeAttribute('data-last-query');
        const nextRemove = next && next.querySelector('[data-pjx-roster-remove]');
        if (nextRemove) nextRemove.focus();
        else if (input) quietFocus(input);
        announceChange(picker);
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

    // Typing already searches through the input's own hx-trigger, so opening
    // here must not ask a second time.
    document.addEventListener('input', function (event) {
        if (!isSearchInput(event.target) || isOpen(event.target)) return;
        const picker = pickerOf(event.target);
        if (picker) setOpen(picker, true);
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

    // closest, not the target: the press usually lands on the row's label or
    // avatar. Enter and Space on a focused row arrive as a click too.
    document.addEventListener('click', function (event) {
        if (!(event.target instanceof Element)) return;
        const row = event.target.closest('[data-pjx-roster-pick]');
        const picker = row && pickerOf(row);
        if (picker) pickRow(picker, row);
    });

    // A swap can bring rows for values already chipped: a route that ignored
    // exclude, or a later page. The paging sentinel swaps outerHTML, so htmx
    // settles the new page inside the mount, not the mount itself.
    document.addEventListener('htmx:afterSettle', function (event) {
        if (!(event.target instanceof Element)) return;
        const picker = pickerOf(event.target);
        if (picker) syncRows(picker);
    });

    document.addEventListener('click', function (event) {
        if (!(event.target instanceof Element)) return;
        const button = event.target.closest('[data-pjx-roster-remove]');
        const chip = button && button.closest('[data-pjx-roster-chip]');
        const picker = chip && pickerOf(chip);
        if (picker) removeChip(picker, chip);
    });

    // Read when the request is built, not at load, so the route sees the
    // chips as they are now and can leave those people out of the rows.
    document.addEventListener('htmx:configRequest', function (event) {
        if (!isSearchInput(event.target)) return;
        const picker = pickerOf(event.target);
        if (picker) event.detail.parameters.exclude = chippedValues(picker).join(',');
    });

    // The query the request sent, not the box's text now: the user may have
    // typed on while it was in flight. A failed or aborted search never set
    // successful, so the rows on screen still answer the old query.
    document.addEventListener('htmx:afterRequest', function (event) {
        if (!isSearchInput(event.target) || event.detail.successful !== true) return;
        event.target.setAttribute('data-last-query', event.detail.requestConfig.parameters.q);
    });

    // A reopen over the text the kept rows were fetched for has nothing new
    // to ask. Typing always searches, even back to the same text, and an
    // emptied list always asks again. Cancelling here, rather than skipping
    // the dispatch, lets htmx release its hx-sync slot for the next search.
    document.addEventListener('htmx:beforeRequest', function (event) {
        const input = event.target;
        if (!isSearchInput(input)) return;
        const trigger = event.detail.requestConfig.triggeringEvent;
        const picker = pickerOf(input);
        if (
            picker &&
            trigger &&
            trigger.type === 'roster-picker-open' &&
            input.value === input.getAttribute('data-last-query') &&
            resultsMount(picker).childElementCount > 0
        ) {
            event.preventDefault();
        }
    });
})();
