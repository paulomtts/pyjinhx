function pxPanelSyncTriggers(hostId, activeKey) {
    document.querySelectorAll(`.px-panel-trigger[data-px-panel-id="${hostId}"]`).forEach((triggerEl) => {
        const isActive = triggerEl.getAttribute('data-px-panel-key') === activeKey;
        triggerEl.setAttribute('aria-selected', isActive ? 'true' : 'false');
        triggerEl.tabIndex = isActive ? 0 : -1;
    });
}

function pxPanelShowPanel(hostRoot, panelKey) {
    const hostId = hostRoot.id;
    if (!hostId) return;
    hostRoot.querySelectorAll('.px-panel__panel').forEach((panelEl) => {
        const key = panelEl.getAttribute('data-px-panel-key');
        if (key === panelKey) {
            panelEl.removeAttribute('hidden');
        } else {
            panelEl.hidden = true;
        }
    });
    pxPanelSyncTriggers(hostId, panelKey);
}

function pxPanelInit() {
    document.querySelectorAll('.px-panel').forEach((root) => {
        const hostId = root.id;
        if (!hostId) return;
        let activeKey = null;
        root.querySelectorAll('.px-panel__panel').forEach((panelEl) => {
            if (!panelEl.hidden) {
                activeKey = panelEl.getAttribute('data-px-panel-key');
            }
        });
        if (activeKey === null) {
            const first = root.querySelector('.px-panel__panel');
            if (first) {
                activeKey = first.getAttribute('data-px-panel-key');
                first.removeAttribute('hidden');
                root.querySelectorAll('.px-panel__panel').forEach((panelEl) => {
                    if (panelEl !== first) panelEl.hidden = true;
                });
            }
        }
        if (activeKey !== null) {
            pxPanelSyncTriggers(hostId, activeKey);
        }
    });
}

document.addEventListener('click', (e) => {
    const trigger = e.target.closest('.px-panel-trigger');
    if (!trigger) return;
    const hostId = trigger.getAttribute('data-px-panel-id');
    const panelKey = trigger.getAttribute('data-px-panel-key');
    if (!hostId || !panelKey) return;
    const hostRoot = document.getElementById(hostId);
    if (!hostRoot || !hostRoot.classList.contains('px-panel')) return;
    e.preventDefault();
    const targetPanel = hostRoot.querySelector(
        '.px-panel__panel[data-px-panel-key="' + panelKey + '"]'
    );
    if (!targetPanel) {
        console.warn('px-panel: no panel for key', panelKey, 'in', hostId);
        return;
    }
    pxPanelShowPanel(hostRoot, panelKey);
});

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', pxPanelInit);
} else {
    pxPanelInit();
}
if (document.body) {
    document.body.addEventListener('htmx:afterSwap', pxPanelInit);
    document.body.addEventListener('htmx:afterSettle', pxPanelInit);
}
