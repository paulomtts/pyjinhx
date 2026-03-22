(function () {
    let _activeCard = null;
    let _activeTrigger = null;
    let _hideTimer = null;
    let _bdGen = 0;

    function _getBackdrop() {
        let bd = document.getElementById('px-popover-backdrop');
        if (!bd) {
            bd = document.createElement('div');
            bd.id = 'px-popover-backdrop';
            bd.className = 'px-popover-backdrop';
            bd.setAttribute('aria-hidden', 'true');
            document.body.appendChild(bd);
        }
        return bd;
    }

    function liftTrigger(trigger) {
        trigger.style.zIndex = 'calc(var(--px-popover-z) + 1)';
    }

    function dropTrigger(trigger) {
        if (trigger) trigger.style.zIndex = '';
    }

    function showBackdrop() {
        _bdGen++;
        const bd = _getBackdrop();
        bd.style.visibility = 'visible';
        requestAnimationFrame(() => requestAnimationFrame(() => {
            bd.classList.add('px-popover-backdrop--visible');
        }));
    }

    function hideBackdrop() {
        const gen = ++_bdGen;
        const bd = document.getElementById('px-popover-backdrop');
        if (!bd) return;
        bd.classList.remove('px-popover-backdrop--visible');
        bd.addEventListener('transitionend', () => {
            if (_bdGen !== gen) return;
            bd.style.visibility = 'hidden';
        }, { once: true });
    }

    function place(card, trigger, x, y) {
        const mode = trigger.dataset.popoverPosition || 'anchor';
        const gap = 10;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const cw = card.offsetWidth;
        const ch = card.offsetHeight;
        let left, top;

        // position:fixed inside a <dialog> (top layer) is contained by the dialog,
        // not the viewport — subtract the dialog's origin to correct coordinates.
        const dialog = card.closest('dialog');
        const dr = dialog ? dialog.getBoundingClientRect() : { left: 0, top: 0 };
        const ox = dr.left;
        const oy = dr.top;

        if (mode === 'follow') {
            left = x - ox + gap;
            top  = y - oy + gap;
            if (left + cw > vw - ox - gap) left = x - ox - cw - gap;
            if (top  + ch > vh - oy - gap) top  = y - oy - ch - gap;
        } else {
            const rect = trigger.getBoundingClientRect();
            left = rect.left - ox;
            top  = rect.bottom - oy + 8;
            if (left + cw > vw - ox - gap) left = vw - ox - cw - gap;
            if (top  + ch > vh - oy - gap) top  = rect.top - oy - ch - 8;
        }

        card.style.left = left + 'px';
        card.style.top  = top  + 'px';
    }

    function showCard(trigger, x, y) {
        const card = trigger.querySelector('.px-popover-card');
        if (!card) return;

        clearTimeout(_hideTimer);

        if (_activeCard && _activeCard !== card) {
            _activeCard.classList.remove('px-popover-card--visible');
            dropTrigger(_activeTrigger);
        }

        _activeCard = card;
        _activeTrigger = trigger;
        card.style.visibility = 'visible';
        card.removeAttribute('aria-hidden');

        if ('popoverBackdrop' in trigger.dataset) {
            liftTrigger(trigger);
            showBackdrop();
        }

        requestAnimationFrame(() => requestAnimationFrame(() => {
            place(card, trigger, x, y);
            card.classList.add('px-popover-card--visible');
        }));
    }

    function hideCard() {
        clearTimeout(_hideTimer);
        _hideTimer = setTimeout(() => {
            if (!_activeCard) return;
            const card = _activeCard;
            const trigger = _activeTrigger;
            _activeCard = null;
            _activeTrigger = null;
            card.classList.remove('px-popover-card--visible');
            card.setAttribute('aria-hidden', 'true');
            card.addEventListener('transitionend', () => {
                if (!card.classList.contains('px-popover-card--visible')) {
                    card.style.visibility = 'hidden';
                }
            }, { once: true });
            dropTrigger(trigger);
            if (trigger && 'popoverBackdrop' in trigger.dataset) hideBackdrop();
        }, 55);
    }

    document.addEventListener('mouseover', e => {
        const trigger = e.target.closest('.px-popover-trigger');
        if (!trigger) return;
        clearTimeout(_hideTimer);
        const card = trigger.querySelector('.px-popover-card');
        if (card && _activeCard !== card) showCard(trigger, e.clientX, e.clientY);
    });

    document.addEventListener('mouseout', e => {
        const trigger = e.target.closest('.px-popover-trigger');
        if (!trigger) return;
        if (!trigger.contains(e.relatedTarget)) hideCard();
    });

    document.addEventListener('mousemove', e => {
        if (!_activeCard || !_activeCard.classList.contains('px-popover-card--visible')) return;
        const trigger = e.target.closest('.px-popover-trigger');
        if (trigger && trigger.dataset.popoverPosition === 'follow') {
            place(_activeCard, trigger, e.clientX, e.clientY);
        }
    });
}());
