(function () {
    window.pjx = window.pjx || {};
    if (pjx._tooltipWired) return;
    pjx._tooltipWired = true;
    let activeTip = null;
    let hideTimer = null;

    function clamp(value, min, max) {
        return Math.max(min, Math.min(value, max));
    }

    /** Bounds the tip must stay inside: the trigger's nearest clipping ancestor. */
    function boundsFor(trigger) {
        let node = trigger.parentElement;
        while (node && node !== document.documentElement) {
            const cs = getComputedStyle(node);
            if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
                return node.getBoundingClientRect();
            }
            node = node.parentElement;
        }
        // Nothing clips the trigger, so the viewport is the bound. We synthesize
        // the rect instead of measuring documentElement: its rect tracks content
        // height, which on a long page is far taller than the visible box.
        return {
            left: 0,
            top: 0,
            right: window.innerWidth,
            bottom: window.innerHeight,
        };
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
        const b = boundsFor(trigger);
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
        tip.style.left = left + 'px';
        tip.style.top = top + 'px';
    }

    function show(root) {
        const tip = root.querySelector('.pjx-tooltip__tip');
        if (!tip) return;
        clearTimeout(hideTimer);
        if (activeTip && activeTip !== tip) {
            activeTip.classList.remove('pjx-tooltip__tip--visible');
            activeTip.setAttribute('hidden', '');
        }
        activeTip = tip;
        tip.removeAttribute('hidden');
        const trig = root.querySelector('.pjx-tooltip__trigger'); if (trig && tip.id) trig.setAttribute('aria-describedby', tip.id);
        requestAnimationFrame(() => {
            place(tip, root);
            tip.classList.add('pjx-tooltip__tip--visible');
        });
    }

    function hide(root) {
        const tip = root.querySelector('.pjx-tooltip__tip');
        if (!tip) return;
        hideTimer = setTimeout(() => {
            tip.classList.remove('pjx-tooltip__tip--visible');
            tip.setAttribute('hidden', '');
            if (activeTip === tip) activeTip = null;
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
            if (activeTip && activeTip.classList.contains('pjx-tooltip__tip--visible')) {
                const root = activeTip.closest('.pjx-tooltip');
                if (root) place(activeTip, root);
            }
        },
        true
    );
}());
