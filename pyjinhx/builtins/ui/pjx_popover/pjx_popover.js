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
// file unchanged. tests/.../test_pjx_popover_assets.py fails if the two drift.

(function () {
    window.pjx = window.pjx || {};
    if (pjx.popover) return;

    const DISMISSIBLE = '.pjx-notification, .pjx-alert, dialog.pjx-modal, dialog.pjx-drawer, [data-pjx-popover-panel]';

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function rootOf(panel) {
        return panel.closest('[data-pjx-popover]') || panel;
    }

    function triggerFor(panel) {
        const root = panel.closest('[data-pjx-popover]');
        return root ? root.querySelector('[data-pjx-toggle]') : null;
    }

    function resolvePanel(idOrEl) {
        if (typeof idOrEl === 'string') return document.getElementById(idOrEl);
        return idOrEl;
    }

    function alignOf(root) {
        return root.classList.contains('pjx-popover--align-end') ? 'end' : 'start';
    }

    function position(panel, root, trigger) {
        const t = trigger.getBoundingClientRect();
        const p = panel.getBoundingClientRect();
        const result = pjx.popoverPosition({
            trigger: { top: t.top, left: t.left, width: t.width, height: t.height },
            panel: { width: p.width, height: p.height },
            viewport: { width: window.innerWidth, height: window.innerHeight },
            align: alignOf(root),
        });
        // Nothing to write when the primitive lands on the static CSS default —
        // an untouched panel keeps the stylesheet in charge, and its rendered
        // markup stays byte-identical to a popover that never needed flipping.
        if (result.adjusted !== true) return;
        panel.style.left = result.left + 'px';
        panel.style.top = result.top + 'px';
        // The align-end rule sets right:0, which would otherwise win the
        // horizontal placement back off the inline left we just wrote.
        panel.style.right = 'auto';
    }

    function open(idOrEl, reason, trigger) {
        const panel = resolvePanel(idOrEl);
        if (!panel || !panel.hidden) return false;
        const target = rootOf(panel);
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(target, 'pjx:popover:before-open', detail, true)) return false;
        panel.hidden = false;
        const t = trigger || triggerFor(panel);
        if (t) t.setAttribute('aria-expanded', 'true');
        // Measured after unhiding (a hidden panel has no box) but in the same
        // synchronous block, so the browser never paints the unpositioned panel.
        if (t) position(panel, target, t);
        fire(target, 'pjx:popover:open', detail);
        return true;
    }

    function close(idOrEl, reason, trigger) {
        const panel = resolvePanel(idOrEl);
        if (!panel || panel.hidden) return false;
        const target = rootOf(panel);
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(target, 'pjx:popover:before-close', detail, true)) return false;
        panel.hidden = true;
        const t = trigger || triggerFor(panel);
        if (t) t.setAttribute('aria-expanded', 'false');
        fire(target, 'pjx:popover:close', detail);
        return true;
    }

    function toggle(idOrEl, reason, trigger) {
        const panel = resolvePanel(idOrEl);
        if (!panel) return false;
        return panel.hidden ? open(panel, reason, trigger) : close(panel, reason, trigger);
    }

    function panelForToggle(toggleEl) {
        const explicit = toggleEl.getAttribute('data-pjx-toggle');
        if (explicit) return document.getElementById(explicit);
        const root = toggleEl.closest('[data-pjx-popover]');
        return root ? root.querySelector('[data-pjx-popover-panel]') : null;
    }

    document.addEventListener('click', (e) => {
        const closer = e.target.closest('[data-pjx-close]');
        if (closer) {
            const dismissible = closer.closest(DISMISSIBLE);
            if (dismissible && dismissible.hasAttribute && dismissible.hasAttribute('data-pjx-popover-panel')) {
                close(dismissible, 'trigger', closer);
                return;
            }
            // Nearest dismissible is another kind (modal, drawer, alert, notification) —
            // fall through to the outside-close loop WITHOUT toggling; no open popover
            // panel would have the click inside its root anyway.
        }
        const toggleEl = e.target.closest('[data-pjx-toggle]');
        const targetPanel = toggleEl ? panelForToggle(toggleEl) : null;
        // Close every open panel whose root doesn't contain the click —
        // also when clicking a trigger (so opening B closes A; nested popovers survive).
        document.querySelectorAll('[data-pjx-popover-panel]:not([hidden])').forEach((panel) => {
            if (panel === targetPanel) return;
            if (!rootOf(panel).contains(e.target)) close(panel, 'backdrop', null);
        });
        if (toggleEl && targetPanel) toggle(targetPanel, 'trigger', toggleEl);
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            const toggleEl = e.target.closest('div[data-pjx-toggle][role="button"]');
            if (toggleEl) {
                e.preventDefault();
                const panel = panelForToggle(toggleEl);
                if (panel) toggle(panel, 'trigger', toggleEl);
                return;
            }
        }
        if (e.key !== 'Escape') return;
        document.querySelectorAll('[data-pjx-popover-panel]:not([hidden])').forEach((panel) => {
            close(panel, 'escape', null);
        });
    });

    pjx.popover = { open: open, close: close, toggle: toggle };
}());
