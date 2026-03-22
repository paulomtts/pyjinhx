function pxRegionSyncTriggers(regionId, activePanel) {
    document.querySelectorAll(`.px-region-trigger[data-px-region="${regionId}"]`).forEach((btn) => {
        const isActive = btn.getAttribute('data-px-region-panel') === activePanel;
        btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        btn.tabIndex = isActive ? 0 : -1;
    });
}

function pxRegionShowPanel(regionRoot, panelKey) {
    const regionId = regionRoot.id;
    if (!regionId) return;
    regionRoot.querySelectorAll('.px-region__panel').forEach((panelEl) => {
        const key = panelEl.getAttribute('data-px-region-panel');
        if (key === panelKey) {
            panelEl.removeAttribute('hidden');
        } else {
            panelEl.hidden = true;
        }
    });
    pxRegionSyncTriggers(regionId, panelKey);
}

function pxRegionInit() {
    document.querySelectorAll('.px-region').forEach((root) => {
        const regionId = root.id;
        if (!regionId) return;
        let activePanel = null;
        root.querySelectorAll('.px-region__panel').forEach((panelEl) => {
            if (!panelEl.hidden) {
                activePanel = panelEl.getAttribute('data-px-region-panel');
            }
        });
        if (activePanel === null) {
            const first = root.querySelector('.px-region__panel');
            if (first) {
                activePanel = first.getAttribute('data-px-region-panel');
                first.removeAttribute('hidden');
                root.querySelectorAll('.px-region__panel').forEach((panelEl) => {
                    if (panelEl !== first) panelEl.hidden = true;
                });
            }
        }
        if (activePanel !== null) {
            pxRegionSyncTriggers(regionId, activePanel);
        }
    });
}

document.addEventListener('click', (e) => {
    const trigger = e.target.closest('.px-region-trigger');
    if (!trigger) return;
    const regionId = trigger.getAttribute('data-px-region');
    const panelKey = trigger.getAttribute('data-px-region-panel');
    if (!regionId || !panelKey) return;
    const regionRoot = document.getElementById(regionId);
    if (!regionRoot || !regionRoot.classList.contains('px-region')) return;
    e.preventDefault();
    const targetPanel = regionRoot.querySelector(
        '.px-region__panel[data-px-region-panel="' + panelKey + '"]'
    );
    if (!targetPanel) {
        console.warn('px-region: no panel for key', panelKey, 'in', regionId);
        return;
    }
    pxRegionShowPanel(regionRoot, panelKey);
});

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', pxRegionInit);
} else {
    pxRegionInit();
}
if (document.body) {
    document.body.addEventListener('htmx:afterSwap', pxRegionInit);
    document.body.addEventListener('htmx:afterSettle', pxRegionInit);
}
