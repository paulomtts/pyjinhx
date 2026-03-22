document.addEventListener('click', (e) => {
    const tab = e.target.closest('.px-tab-group__tab');
    if (!tab) return;
    const root = tab.closest('.px-tab-group');
    if (!root || !root.id) return;
    e.preventDefault();
    const tabs = [...root.querySelectorAll('.px-tab-group__tab')];
    const panels = [...root.querySelectorAll('.px-tab-group__panel')];
    const index = tabs.indexOf(tab);
    if (index < 0) return;
    tabs.forEach((t, i) => {
        t.setAttribute('aria-selected', i === index ? 'true' : 'false');
        t.tabIndex = i === index ? 0 : -1;
    });
    panels.forEach((p, i) => {
        if (i === index) {
            p.removeAttribute('hidden');
        } else {
            p.hidden = true;
        }
    });
});
