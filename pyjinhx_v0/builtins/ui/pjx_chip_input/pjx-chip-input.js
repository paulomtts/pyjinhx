(function () {
    window.pjx = window.pjx || {};
    if (pjx._chipInputWired) return;
    pjx._chipInputWired = true;

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function getRoot(el) {
        return el.closest('[data-pjx-chip-input]');
    }

    function isDisabled(root) {
        return root.hasAttribute('data-disabled');
    }

    function isDuplicate(root, value) {
        return Array.from(root.querySelectorAll('input[type="hidden"]'))
            .some(function (inp) { return inp.value === value; });
    }

    function getRemoveLabel(root) {
        const existing = root.querySelector('[data-pjx-chip-remove]');
        if (existing) return existing.getAttribute('aria-label') || 'Remove';
        return root.dataset.removeLabel || 'Remove';
    }

    function buildChip(root, value) {
        const chip = document.createElement('span');
        chip.className = 'pjx-chip-input__chip';
        chip.setAttribute('data-pjx-chip', '');

        const label = document.createElement('span');
        label.className = 'pjx-chip-input__label';
        label.textContent = value;
        chip.appendChild(label);

        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = root.dataset.name;
        hidden.value = value;
        chip.appendChild(hidden);

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'pjx-chip-input__remove';
        btn.setAttribute('data-pjx-chip-remove', '');
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
        if (!fire(root, 'pjx:chip-input:before-add', { value: value }, true)) return;
        const chip = buildChip(root, value);
        root.insertBefore(chip, field);
        field.value = '';
        fire(root, 'pjx:chip-input:add', { value: value });
    }

    function removeChip(chip) {
        const root = getRoot(chip);
        if (!root || isDisabled(root)) return;
        const hidden = chip.querySelector('input[type="hidden"]');
        const value = hidden ? hidden.value : '';
        if (!fire(root, 'pjx:chip-input:before-remove', { value: value }, true)) return;
        chip.remove();
        fire(root, 'pjx:chip-input:remove', { value: value });
    }

    document.addEventListener('keydown', function (e) {
        if (e.isComposing) return;
        if (!e.target.classList.contains('pjx-chip-input__field')) return;
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
            const chips = root.querySelectorAll('[data-pjx-chip]');
            if (chips.length > 0) {
                removeChip(chips[chips.length - 1]);
            }
        }
    });

    document.addEventListener('focusout', function (e) {
        if (!e.target.classList.contains('pjx-chip-input__field')) return;
        const root = getRoot(e.target);
        if (!root || isDisabled(root)) return;
        commit(root, e.target);
    });

    document.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-pjx-chip-remove]');
        if (!btn) return;
        const chip = btn.closest('[data-pjx-chip]');
        if (chip) removeChip(chip);
    });

    // Commit pending text on form submit (Safari never fires focusout on button click).
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form.querySelectorAll) return;
        form.querySelectorAll('.pjx-chip-input__field').forEach(function (field) {
            const root = field.closest('[data-pjx-chip-input]');
            if (root && !root.hasAttribute('data-disabled') && field.value.trim()) {
                commit(root, field);
            }
        });
    });
}());
