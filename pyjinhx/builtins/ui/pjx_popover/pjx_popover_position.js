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
