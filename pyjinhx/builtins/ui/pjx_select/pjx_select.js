(function () {
    // Pure geometry, deliberately DOM-free: callers measure and apply, this
    // only resolves numbers, so a dropdown with its own rect source (or a
    // unit test with synthetic rects) can reuse it unchanged.
    window.pjx = window.pjx || {};

    function clamp(value, min, max) {
        return Math.max(min, Math.min(value, max));
    }

    /**
     * Resolve where a floating panel goes relative to its trigger's top-left corner.
     *
     * Returns { align, placement, left, top, adjusted }. `left`/`top` are px
     * offsets from the trigger's top-left; with no overflow they reproduce the
     * static CSS default exactly and `adjusted` is false, so a caller may skip
     * writing inline styles altogether.
     *
     * This file is not shipped by the asset walk — only the stem-matched
     * pjx_popover.js is co-located with PJXPopover — so whoever wires the
     * primitive into the popover controller also arranges its delivery.
     */
    function popoverPosition(options) {
        const trigger = options.trigger;
        const panel = options.panel;
        const viewport = options.viewport;
        const gap = options.gap === undefined ? 4 : options.gap;
        const padding = options.padding === undefined ? 8 : options.padding;
        const requested = options.align === 'end' ? 'end' : 'start';

        const startX = trigger.left;
        const endX = trigger.left + trigger.width - panel.width;
        let align = requested;
        let x = align === 'start' ? startX : endX;

        // Flip only when the other side actually fits: on a viewport narrower
        // than the panel both sides overflow, and flipping there would just
        // trade one overflow for another before the clamp fallback runs.
        // The overflow check itself must use the raw viewport edges, not the
        // padded inset: padding is a last-resort fallback distance, not the
        // threshold for "does this need flipping" (a padded threshold flips
        // align:"end" cases that are fully on-screen, e.g. a 200px panel
        // right-aligned to a trigger at x=100 in a 1000px viewport sits at
        // x=0 — on-screen but under an 8px padding threshold).
        if (align === 'start' && x + panel.width > viewport.width) {
            if (endX >= 0) {
                align = 'end';
                x = endX;
            }
        } else if (align === 'end' && x < 0) {
            if (startX + panel.width <= viewport.width) {
                align = 'start';
                x = startX;
            }
        }

        // The padded clamp is a last-resort fallback for when the viewport is
        // narrower than the panel and flipping found no non-overflowing side.
        // It must not run on values that are already on-screen, or it would
        // pull the no-overflow default in off the raw viewport edge (the same
        // padding-vs-raw-edge conflation as the flip check above).
        if (x < 0 || x + panel.width > viewport.width) {
            x = clamp(x, padding, viewport.width - panel.width - padding);
        }

        const belowY = trigger.top + trigger.height + gap;
        const aboveY = trigger.top - panel.height - gap;
        let placement = 'below';
        let y = belowY;

        // Same raw-edge-vs-padding split as the horizontal half: the flip
        // check uses the true viewport bound, and the padded clamp only
        // engages as a fallback when the chosen placement still overflows.
        if (belowY + panel.height > viewport.height && aboveY >= 0) {
            placement = 'above';
            y = aboveY;
        }
        if (y < 0 || y + panel.height > viewport.height) {
            y = clamp(y, padding, viewport.height - panel.height - padding);
        }

        const defaultX = requested === 'start' ? startX : endX;
        return {
            align: align,
            placement: placement,
            left: x - trigger.left,
            top: y - trigger.top,
            adjusted: align !== requested || x !== defaultX || y !== belowY,
        };
    }

    pjx.popoverPosition = popoverPosition;
}());

// ^ Verbatim copy of pjx_popover_position.js. The asset walk ships one script
// per class by stem, so the shared primitive has no slot of its own; it is
// duplicated here rather than rewritten so PJXSelect can reuse the original
// file unchanged. tests/.../test_pjx_select_assets.py fails if the two drift.

(function () {
    window.pjx = window.pjx || {};
    if (pjx._selectWired) return;
    pjx._selectWired = true;

    function rootOf(el) {
        return el.closest('[data-pjx-select]');
    }

    function partsOf(root) {
        return {
            trigger: root.querySelector('[data-pjx-select-trigger]'),
            panel: root.querySelector('[data-pjx-select-panel]'),
            label: root.querySelector('.pjx-select__label'),
            native: root.querySelector('select'),
        };
    }

    function position(panel, trigger) {
        const t = trigger.getBoundingClientRect();
        const p = panel.getBoundingClientRect();
        const result = pjx.popoverPosition({
            trigger: { top: t.top, left: t.left, width: t.width, height: t.height },
            panel: { width: p.width, height: p.height },
            viewport: { width: window.innerWidth, height: window.innerHeight },
            align: 'start',
        });
        // A prior open may have left inline coordinates behind; drop them so a
        // since-fixed layout falls back to the CSS default.
        panel.removeAttribute('style');
        if (result.adjusted !== true) return;
        panel.style.left = result.left + 'px';
        panel.style.top = result.top + 'px';
    }

    function open(root) {
        const parts = partsOf(root);
        if (!parts.panel || !parts.panel.hidden) return;
        parts.panel.hidden = false;
        if (parts.trigger) {
            parts.trigger.setAttribute('aria-expanded', 'true');
            // Measured after unhiding (a hidden panel has no box) but in the
            // same synchronous block, so the unpositioned panel never paints.
            position(parts.panel, parts.trigger);
        }
    }

    function close(root) {
        const parts = partsOf(root);
        if (!parts.panel || parts.panel.hidden) return;
        parts.panel.hidden = true;
        parts.panel.removeAttribute('style');
        // Reopening starts from the whole list: a stale query would silently
        // hide options the user never chose to filter out.
        const filter = root.querySelector('[data-pjx-select-filter]');
        if (filter) {
            filter.value = '';
            applyFilter(root, '');
        }
        if (parts.trigger) parts.trigger.setAttribute('aria-expanded', 'false');
    }

    function isMultiple(root) {
        return root.hasAttribute('data-multiple');
    }

    function selectedOptions(root) {
        return Array.prototype.slice.call(
            root.querySelectorAll('[data-pjx-select-option][aria-selected="true"]')
        );
    }

    function labelOf(option) {
        return option.textContent.trim();
    }

    // Visual-only: option buttons are hidden, never deselected, and the native
    // <select> keeps every one of its options so a submit still posts them.
    function applyFilter(root, query) {
        const needle = query.trim().toLowerCase();
        root.querySelectorAll('[data-pjx-select-option]').forEach(function (option) {
            option.hidden = needle !== '' && labelOf(option).toLowerCase().indexOf(needle) === -1;
        });
    }

    // The native <select> is the form's source of truth in both modes, so it is
    // re-derived from the option buttons rather than patched incrementally.
    function syncNative(root, parts) {
        if (!parts.native) return;
        const values = selectedOptions(root).map(function (opt) {
            return opt.getAttribute('data-value');
        });
        Array.prototype.forEach.call(parts.native.options, function (nativeOption) {
            nativeOption.selected = values.indexOf(nativeOption.value) !== -1;
        });
    }

    // Mirrors the template's trigger branch: 2+ selections become a chip row,
    // 0 or 1 stay plain text. Chips are built node-by-node with textContent so
    // a label containing markup can never become markup.
    function renderTrigger(root, parts) {
        if (!parts.label) return;
        const chosen = selectedOptions(root);
        if (chosen.length < 2) {
            parts.label.textContent = chosen.length
                ? labelOf(chosen[0])
                : root.getAttribute('data-placeholder') || '';
            return;
        }
        const row = document.createElement('span');
        row.className = 'pjx-select__chips';
        chosen.forEach(function (option) {
            const chip = document.createElement('span');
            chip.className = 'pjx-chip-input__chip';
            const label = document.createElement('span');
            label.className = 'pjx-chip-input__label';
            label.textContent = labelOf(option);
            chip.appendChild(label);
            row.appendChild(chip);
        });
        parts.label.textContent = '';
        parts.label.appendChild(row);
    }

    function toggle(root, option) {
        const parts = partsOf(root);
        const next = option.getAttribute('aria-selected') !== 'true';
        option.setAttribute('aria-selected', next ? 'true' : 'false');
        const box = option.querySelector('.pjx-select__checkbox');
        if (box) box.checked = next;
        syncNative(root, parts);
        renderTrigger(root, parts);
    }

    function select(root, value) {
        const parts = partsOf(root);
        root.querySelectorAll('[data-pjx-select-option]').forEach(function (opt) {
            const isIt = opt.getAttribute('data-value') === value;
            opt.setAttribute('aria-selected', isIt ? 'true' : 'false');
        });
        syncNative(root, parts);
        renderTrigger(root, parts);
    }

    document.addEventListener('click', function (e) {
        const option = e.target.closest('[data-pjx-select-option]');
        if (option) {
            const root = rootOf(option);
            // A disabled select never opens its panel, so this branch is
            // unreachable while disabled — the guard just makes that explicit.
            if (root && !root.hasAttribute('data-disabled')) {
                if (isMultiple(root)) {
                    // Multi-select stays open: picking several values from one
                    // opening is the whole point of the mode.
                    toggle(root, option);
                } else {
                    select(root, option.getAttribute('data-value'));
                    close(root);
                }
            }
            return;
        }
        const trigger = e.target.closest('[data-pjx-select-trigger]');
        const targetRoot = trigger ? rootOf(trigger) : null;
        // Close every open select whose root doesn't contain the click, also
        // when clicking another select's trigger (opening B closes A).
        document.querySelectorAll('[data-pjx-select]').forEach(function (root) {
            if (root === targetRoot) return;
            if (!root.contains(e.target)) close(root);
        });
        if (!targetRoot || targetRoot.hasAttribute('data-disabled')) return;
        const panel = targetRoot.querySelector('[data-pjx-select-panel]');
        if (panel && panel.hidden) open(targetRoot);
        else close(targetRoot);
    });

    document.addEventListener('input', function (e) {
        const filter = e.target.closest('[data-pjx-select-filter]');
        if (!filter) return;
        const root = rootOf(filter);
        if (root) applyFilter(root, filter.value);
    });

    // --- keyboard navigation -------------------------------------------
    // Option buttons are natively focusable, so focus moves with .focus()
    // alone; no roving tabindex. A select panel is a transient popup whose
    // only tab stop is the trigger, unlike a tablist that must stay in the
    // page's tab order with exactly one active tab.

    function visibleOptions(root) {
        return Array.prototype.slice.call(
            root.querySelectorAll('[data-pjx-select-option]:not([hidden]):not([disabled])')
        );
    }

    function moveFocus(root, from, delta) {
        const options = visibleOptions(root);
        if (!options.length) return;
        const at = options.indexOf(from);
        // An unknown `from` (focus in the filter box, or a node the filter
        // just hid) enters the list from whichever end the caller is heading.
        const next = at === -1
            ? (delta > 0 ? 0 : options.length - 1)
            : (at + delta + options.length) % options.length;
        options[next].focus();
    }

    function focusEdge(root, last) {
        const options = visibleOptions(root);
        if (!options.length) return;
        options[last ? options.length - 1 : 0].focus();
    }

    let typeAhead = '';
    let typeAheadTimer = null;

    function pushTypeAhead(ch) {
        typeAhead += ch;
        if (typeAheadTimer) clearTimeout(typeAheadTimer);
        // A pause means the next keystroke starts a new word, not a longer
        // prefix of the old one.
        typeAheadTimer = setTimeout(function () {
            typeAhead = '';
            typeAheadTimer = null;
        }, 500);
        return typeAhead;
    }

    function typeAheadTarget(root, from, needle) {
        const options = visibleOptions(root);
        if (!options.length) return null;
        const start = options.indexOf(from);
        const prefix = needle.toLowerCase();
        // Search starts *after* the focused option so repeating a letter
        // cycles through the options sharing that initial.
        for (let step = 1; step <= options.length; step += 1) {
            const option = options[(start + step + options.length) % options.length];
            if (labelOf(option).toLowerCase().indexOf(prefix) === 0) return option;
        }
        return null;
    }

    function dismiss(root) {
        const trigger = root.querySelector('[data-pjx-select-trigger]');
        close(root);
        if (trigger) trigger.focus();
    }

    function commitOption(root, option) {
        if (isMultiple(root)) {
            // Multi-select stays open and keeps focus put, so the next Enter
            // lands on the option the user is still looking at.
            toggle(root, option);
            return;
        }
        select(root, option.getAttribute('data-value'));
        dismiss(root);
    }

    function onTriggerKey(e, root) {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            open(root);
            const options = visibleOptions(root);
            if (!options.length) return;
            options[e.key === 'ArrowUp' ? options.length - 1 : 0].focus();
        }
    }

    document.addEventListener('keydown', function (e) {
        if (e.isComposing) return;
        if (!e.target.closest) return;
        const root = rootOf(e.target);
        if (!root || root.hasAttribute('data-disabled')) return;

        if (e.key === 'Escape') {
            e.preventDefault();
            dismiss(root);
            return;
        }

        const option = e.target.closest('[data-pjx-select-option]');
        if (!option) {
            // The filter box owns its own keystrokes: its `input` listener is
            // the search, so type-ahead would only fight it.
            if (e.target.closest('[data-pjx-select-filter]')) {
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    focusEdge(root, false);
                }
                return;
            }
            if (e.target.closest('[data-pjx-select-trigger]')) onTriggerKey(e, root);
            return;
        }

        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            moveFocus(root, option, e.key === 'ArrowDown' ? 1 : -1);
            return;
        }
        if (e.key === 'Home' || e.key === 'End') {
            e.preventDefault();
            focusEdge(root, e.key === 'End');
            return;
        }
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            commitOption(root, option);
            return;
        }
        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
            const target = typeAheadTarget(root, option, pushTypeAhead(e.key));
            // No match leaves focus alone; the buffer still holds, so the
            // user can back out of a typo by pausing.
            if (target) {
                e.preventDefault();
                target.focus();
            }
        }
    });
}());
