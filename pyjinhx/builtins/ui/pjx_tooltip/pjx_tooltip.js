(function () {
    window.pjx = window.pjx || {};
    if (pjx._tooltipWired) return;
    pjx._tooltipWired = true;
    let activeTip = null;
    let activeRoot = null;
    let activeBackdrop = null;
    let hideTimer = null;
    // Keyed by root, not tip: once portalled the tip is no longer a
    // descendant of root, so root.querySelector('.pjx-tooltip__tip') can no
    // longer find it — every lookup goes through tipFor()/portalled instead.
    const portalled = new WeakMap();
    // Pending unportalTip() timers, keyed by root: show() cancels a root's
    // timer when it reactivates a tip mid fade-out, so a stale timer can't
    // reparent a tip that's visible again.
    const unportalTimers = new WeakMap();

    function isPortalled(root) {
        return root.dataset.pjxTooltipPortal !== undefined;
    }

    function tipFor(root) {
        return root.querySelector('.pjx-tooltip__tip') || (portalled.get(root) || {}).tip || null;
    }

    /**
     * Reparent the tip to document.body so it escapes a clipping (or
     * fixed-positioning-containing) ancestor entirely, instead of being
     * clamped into that ancestor's bounds.
     */
    function portalTip(tip, root) {
        if (!isPortalled(root) || portalled.has(root)) return;
        portalled.set(root, { tip, parent: tip.parentElement, next: tip.nextSibling });
        document.body.appendChild(tip);
    }

    function unportalTip(root) {
        const entry = portalled.get(root);
        if (!entry) return;
        portalled.delete(root);
        entry.parent.insertBefore(entry.tip, entry.next);
    }

    function hideBackdrop(backdrop) {
        backdrop.classList.remove('pjx-tooltip__backdrop--visible');
        backdrop.setAttribute('hidden', '');
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(value, max));
    }

    /**
     * Bounds the tip must stay inside: the trigger's nearest clipping ancestor,
     * intersected with the viewport. A clipping ancestor (e.g. a wide/tall
     * scrollable table wrapper) can itself extend past the visible window, so
     * clamping to it alone would still let the tip spill off-screen.
     */
    function boundsFor(trigger, portalled) {
        // We synthesize the viewport rect instead of measuring documentElement:
        // its rect tracks content height, which on a long page is far taller
        // than the visible box.
        const viewport = {
            left: 0,
            top: 0,
            right: window.innerWidth,
            bottom: window.innerHeight,
        };
        if (portalled) return viewport;
        let node = trigger.parentElement;
        while (node && node !== document.documentElement) {
            const cs = getComputedStyle(node);
            if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
                const rect = node.getBoundingClientRect();
                return {
                    left: Math.max(rect.left, viewport.left),
                    top: Math.max(rect.top, viewport.top),
                    right: Math.min(rect.right, viewport.right),
                    bottom: Math.min(rect.bottom, viewport.bottom),
                };
            }
            node = node.parentElement;
        }
        return viewport;
    }

    function place(tip, root) {
        let placement = root.dataset.pjxTooltipPlacement || 'top';
        const gapRaw = getComputedStyle(document.documentElement)
            .getPropertyValue('--pjx-tooltip-gap')
            .trim();
        const gap = parseInt(gapRaw, 10) || 6;
        const trigger = root.querySelector('.pjx-tooltip__trigger');
        if (!trigger) return;
        const tr = trigger.getBoundingClientRect();
        const tw = tip.offsetWidth;
        const th = tip.offsetHeight;
        const b = boundsFor(trigger, isPortalled(root));
        let top;
        let left;

        // Flip to the opposite side of the same axis when the requested side
        // overflows the bounds and the opposite one actually fits. The checks
        // use the raw bound edges, not the padded ones below: the padding is a
        // last-resort clamp distance, and treating it as the flip threshold
        // would flip placements that are still fully inside the container.
        if (placement === 'top' && tr.top - th - gap < b.top) {
            if (tr.bottom + gap + th <= b.bottom) placement = 'bottom';
        } else if (placement === 'bottom' && tr.bottom + gap + th > b.bottom) {
            if (tr.top - th - gap >= b.top) placement = 'top';
        } else if (placement === 'start' && tr.left - tw - gap < b.left) {
            if (tr.right + gap + tw <= b.right) placement = 'end';
        } else if (placement === 'end' && tr.right + gap + tw > b.right) {
            if (tr.left - tw - gap >= b.left) placement = 'start';
        }

        if (placement === 'bottom') {
            top = tr.bottom + gap;
            left = tr.left + tr.width / 2 - tw / 2;
        } else if (placement === 'start') {
            top = tr.top + tr.height / 2 - th / 2;
            left = tr.left - tw - gap;
        } else if (placement === 'end') {
            top = tr.top + tr.height / 2 - th / 2;
            left = tr.right + gap;
        } else {
            top = tr.top - th - gap;
            left = tr.left + tr.width / 2 - tw / 2;
        }

        left = clamp(left, b.left + 8, b.right - tw - 8);
        top = clamp(top, b.top + 8, b.bottom - th - 8);

        // The bounds clamp above has no notion of the trigger itself, so in
        // the reduced-space case (neither side fully fits) it can push the
        // tip on top of the trigger it's describing. Re-clamp against the
        // trigger's own rect on the axis the chosen placement sits on, even
        // if that pushes the tip further past the bounds edge.
        if (placement === 'top') {
            top = Math.min(top, tr.top - th - gap);
        } else if (placement === 'bottom') {
            top = Math.max(top, tr.bottom + gap);
        } else if (placement === 'start') {
            left = Math.min(left, tr.left - tw - gap);
        } else if (placement === 'end') {
            left = Math.max(left, tr.right + gap);
        }

        tip.style.left = left + 'px';
        tip.style.top = top + 'px';
    }

    function show(root) {
        const tip = tipFor(root);
        if (!tip) return;
        const backdrop = root.querySelector('.pjx-tooltip__backdrop');
        clearTimeout(hideTimer);
        clearTimeout(unportalTimers.get(root));
        if (activeTip && activeTip !== tip) {
            activeTip.classList.remove('pjx-tooltip__tip--visible');
            activeTip.setAttribute('hidden', '');
            clearTimeout(unportalTimers.get(activeRoot));
            unportalTip(activeRoot);
        }
        if (activeBackdrop && activeBackdrop !== backdrop) hideBackdrop(activeBackdrop);
        activeTip = tip;
        activeRoot = root;
        activeBackdrop = backdrop;
        tip.removeAttribute('hidden');
        portalTip(tip, root);
        if (backdrop) backdrop.removeAttribute('hidden');
        const trig = root.querySelector('.pjx-tooltip__trigger'); if (trig && tip.id) trig.setAttribute('aria-describedby', tip.id);
        requestAnimationFrame(() => {
            // Visibility first, position second. place() measures live layout,
            // and a throw inside a rAF callback is swallowed by the browser and
            // abandons the rest of the callback — with the ordering reversed, a
            // measurement that misbehaves (a trigger nested under a top-layer
            // <dialog>, say) leaves the tip with its hidden attribute already
            // removed but no visible class, i.e. permanently invisible. A bad
            // measurement must cost position, never visibility.
            tip.classList.add('pjx-tooltip__tip--visible');
            if (backdrop) backdrop.classList.add('pjx-tooltip__backdrop--visible');
            place(tip, root);
        });
    }

    function hide(root) {
        const tip = tipFor(root);
        if (!tip) return;
        const backdrop = root.querySelector('.pjx-tooltip__backdrop');
        hideTimer = setTimeout(() => {
            tip.classList.remove('pjx-tooltip__tip--visible');
            tip.setAttribute('hidden', '');
            // Defer unportalTip() until the fade-out transition has actually
            // finished: reparenting synchronously here changes the tip's
            // layout box (unconstrained body -> clamped narrow ancestor)
            // while it's still visibly fading, producing a reflow mid-fade.
            unportalTimers.set(root, setTimeout(() => unportalTip(root), 120));
            if (backdrop) hideBackdrop(backdrop);
            if (activeTip === tip) {
                activeTip = null;
                activeRoot = null;
            }
            if (activeBackdrop === backdrop) activeBackdrop = null;
        }, 80);
    }

    document.addEventListener('focusin', (e) => {
        const root = e.target.closest('.pjx-tooltip');
        if (!root || !root.contains(e.target)) return;
        if (!e.target.closest('.pjx-tooltip__trigger')) return;
        show(root);
    });

    document.addEventListener('focusout', (e) => {
        const root = e.target.closest('.pjx-tooltip');
        if (!root) return;
        setTimeout(() => {
            if (!root.contains(document.activeElement)) hide(root);
        }, 0);
    });

    document.addEventListener('mouseover', (e) => {
        const root = e.target.closest('.pjx-tooltip');
        if (!root) return;
        if (!root.contains(e.target)) return;
        show(root);
    });

    document.addEventListener('mouseout', (e) => {
        const root = e.target.closest('.pjx-tooltip');
        if (!root) return;
        if (!root.contains(e.relatedTarget)) hide(root);
    });

    window.addEventListener(
        'scroll',
        () => {
            if (activeTip && activeRoot && activeTip.classList.contains('pjx-tooltip__tip--visible')) {
                place(activeTip, activeRoot);
            }
        },
        true
    );
}());
