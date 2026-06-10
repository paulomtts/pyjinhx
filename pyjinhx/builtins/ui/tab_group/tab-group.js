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
        if (panels[index].hidden) {
            if (!fire(panels[index], 'px:before-reveal', { reason: 'trigger', trigger: tab }, true)) return;
        }
        tabs.forEach((t, i) => {
            t.setAttribute('aria-selected', i === index ? 'true' : 'false');
            t.tabIndex = i === index ? 0 : -1;
        });
        panels.forEach((p, i) => { p.hidden = i !== index; });
        fire(panels[index], 'px:reveal', { reason: 'trigger', trigger: tab });
    });
}());
