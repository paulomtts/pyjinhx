(function () {
    window.px = window.px || {};
    if (px._chipInputWired) return;
    px._chipInputWired = true;

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function getRoot(el) {
        return el.closest('[data-px-chip-input]');
    }

    function isDisabled(root) {
        return root.hasAttribute('data-disabled');
    }

    function isDuplicate(root, value) {
        return Array.from(root.querySelectorAll('input[type="hidden"]'))
            .some(function (inp) { return inp.value === value; });
    }

    function getRemoveLabel(root) {
        const existing = root.querySelector('[data-px-chip-remove]');
        if (existing) return existing.getAttribute('aria-label') || 'Remove';
        return root.dataset.removeLabel || 'Remove';
    }

    function buildChip(root, value) {
        const chip = document.createElement('span');
        chip.className = 'px-chip-input__chip';
        chip.setAttribute('data-px-chip', '');

        const label = document.createElement('span');
        label.className = 'px-chip-input__label';
        label.textContent = value;
        chip.appendChild(label);

        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = root.dataset.name;
        hidden.value = value;
        chip.appendChild(hidden);

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'px-chip-input__remove';
        btn.setAttribute('data-px-chip-remove', '');
        btn.setAttribute('aria-label', getRemoveLabel(root));
        btn.textContent = '✕';
        chip.appendChild(btn);

        return chip;
    }

    function commit(root, field) {
        const value = field.value.trim().replace(/,$/, '');
        if (!value) return;
        if (isDuplicate(root, value)) {
            field.value = '';
            return;
        }
        if (!fire(root, 'px:chip-input:before-add', { value: value }, true)) return;
        const chip = buildChip(root, value);
        root.insertBefore(chip, field);
        field.value = '';
        fire(root, 'px:chip-input:add', { value: value });
    }

    function removeChip(chip) {
        const root = getRoot(chip);
        if (!root || isDisabled(root)) return;
        const hidden = chip.querySelector('input[type="hidden"]');
        const value = hidden ? hidden.value : '';
        if (!fire(root, 'px:chip-input:before-remove', { value: value }, true)) return;
        chip.remove();
        fire(root, 'px:chip-input:remove', { value: value });
    }

    document.addEventListener('keydown', function (e) {
        if (e.isComposing) return;
        if (!e.target.classList.contains('px-chip-input__field')) return;
        const root = getRoot(e.target);
        if (!root || isDisabled(root)) return;

        if (e.key === 'Enter') {
            if (e.target.value.trim()) {
                e.preventDefault();
                commit(root, e.target);
            }
        } else if (e.key === ',') {
            e.preventDefault();
            commit(root, e.target);
        } else if (e.key === 'Backspace' && e.target.value === '') {
            const chips = root.querySelectorAll('[data-px-chip]');
            if (chips.length > 0) {
                removeChip(chips[chips.length - 1]);
            }
        }
    });

    document.addEventListener('focusout', function (e) {
        if (!e.target.classList.contains('px-chip-input__field')) return;
        const root = getRoot(e.target);
        if (!root || isDisabled(root)) return;
        commit(root, e.target);
    });

    document.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-px-chip-remove]');
        if (!btn) return;
        const chip = btn.closest('[data-px-chip]');
        if (chip) removeChip(chip);
    });

    // Commit pending text on form submit (Safari never fires focusout on button click).
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form.querySelectorAll) return;
        form.querySelectorAll('.px-chip-input__field').forEach(function (field) {
            const root = field.closest('[data-px-chip-input]');
            if (root && !root.hasAttribute('data-disabled') && field.value.trim()) {
                commit(root, field);
            }
        });
    });
}());
