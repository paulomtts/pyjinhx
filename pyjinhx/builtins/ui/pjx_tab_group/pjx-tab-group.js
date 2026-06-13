(function () {
    window.pjx = window.pjx || {};
    if (pjx._tabGroupWired) return;
    pjx._tabGroupWired = true;

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    document.addEventListener('click', (e) => {
        const tab = e.target.closest('.pjx-tab-group__tab');
        if (!tab) return;
        const root = tab.closest('.pjx-tab-group');
        if (!root || !root.id) return;
        e.preventDefault();
        const tabs = [...root.querySelectorAll('.pjx-tab-group__tab')];
        const panels = [...root.querySelectorAll('.pjx-tab-group__panel')];
        const index = tabs.indexOf(tab);
        if (index < 0 || !panels[index]) return;
        if (!panels[index].hidden) return; // already active: nothing to announce
        const detail = { reason: 'trigger', trigger: tab };
        if (!fire(panels[index], 'pjx:before-reveal', detail, true)) return;
        tabs.forEach((t, i) => {
            t.setAttribute('aria-selected', i === index ? 'true' : 'false');
            t.tabIndex = i === index ? 0 : -1;
        });
        panels.forEach((p, i) => {
            p.hidden = i !== index;
            if (i !== index) p.removeAttribute('data-pjx-revealed');
        });
        panels[index].setAttribute('data-pjx-revealed', '');
        fire(panels[index], 'pjx:reveal', detail);
    });

    // Announce the initially visible panel of each tab group exactly once,
    // so PJXLazyPanel(when="reveal") works in default tabs (parity with pjx-panel.js).
    function pxTabGroupInit() {
        document.querySelectorAll('.pjx-tab-group').forEach((root) => {
            const visible = root.querySelector('.pjx-tab-group__panel:not([hidden])');
            if (visible && !visible.hasAttribute('data-pjx-revealed')) {
                visible.setAttribute('data-pjx-revealed', '');
                fire(visible, 'pjx:reveal', { reason: 'api', trigger: null });
            }
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', pxTabGroupInit);
    } else {
        pxTabGroupInit();
    }
    if (document.body) {
        document.body.addEventListener('htmx:afterSwap', pxTabGroupInit);
        document.body.addEventListener('htmx:afterSettle', pxTabGroupInit);
    }
}());
