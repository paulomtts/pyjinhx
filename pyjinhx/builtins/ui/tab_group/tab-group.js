(function () {
    window.px = window.px || {};
    if (px._tabGroupWired) return;
    px._tabGroupWired = true;

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    document.addEventListener('click', (e) => {
        const tab = e.target.closest('.px-tab-group__tab');
        if (!tab) return;
        const root = tab.closest('.px-tab-group');
        if (!root || !root.id) return;
        e.preventDefault();
        const tabs = [...root.querySelectorAll('.px-tab-group__tab')];
        const panels = [...root.querySelectorAll('.px-tab-group__panel')];
        const index = tabs.indexOf(tab);
        if (index < 0 || !panels[index]) return;
        if (!panels[index].hidden) return; // already active: nothing to announce
        const detail = { reason: 'trigger', trigger: tab };
        if (!fire(panels[index], 'px:before-reveal', detail, true)) return;
        tabs.forEach((t, i) => {
            t.setAttribute('aria-selected', i === index ? 'true' : 'false');
            t.tabIndex = i === index ? 0 : -1;
        });
        panels.forEach((p, i) => {
            p.hidden = i !== index;
            if (i !== index) p.removeAttribute('data-px-revealed');
        });
        panels[index].setAttribute('data-px-revealed', '');
        fire(panels[index], 'px:reveal', detail);
    });

    // Announce the initially visible panel of each tab group exactly once,
    // so LazyPanel(when="reveal") works in default tabs (parity with panel.js).
    function pxTabGroupInit() {
        document.querySelectorAll('.px-tab-group').forEach((root) => {
            const visible = root.querySelector('.px-tab-group__panel:not([hidden])');
            if (visible && !visible.hasAttribute('data-px-revealed')) {
                visible.setAttribute('data-px-revealed', '');
                fire(visible, 'px:reveal', { reason: 'api', trigger: null });
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
