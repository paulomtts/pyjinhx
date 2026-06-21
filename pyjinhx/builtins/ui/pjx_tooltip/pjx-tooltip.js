(function () {
    window.pjx = window.pjx || {};
    if (pjx._tooltipWired) return;
    pjx._tooltipWired = true;
    let activeTip = null;
    let hideTimer = null;

    function place(tip, root) {
        const placement = root.dataset.pjxTooltipPlacement || 'top';
        const gapRaw = getComputedStyle(document.documentElement)
            .getPropertyValue('--pjx-tooltip-gap')
            .trim();
        const gap = parseInt(gapRaw, 10) || 6;
        const trigger = root.querySelector('.pjx-tooltip__trigger');
        if (!trigger) return;
        const tr = trigger.getBoundingClientRect();
        const tw = tip.offsetWidth;
        const th = tip.offsetHeight;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        let top;
        let left;

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

        left = Math.max(8, Math.min(left, vw - tw - 8));
        top = Math.max(8, Math.min(top, vh - th - 8));
        tip.style.left = left + 'pjx';
        tip.style.top = top + 'pjx';
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
