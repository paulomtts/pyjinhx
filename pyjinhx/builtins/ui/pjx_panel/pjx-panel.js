(function () {
    window.pjx = window.pjx || {};
    if (pjx._panelWired) return;
    pjx._panelWired = true;

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function pxPanelSyncTriggers(hostId, activeKey) {
        document.querySelectorAll(`.pjx-panel-trigger[data-pjx-panel-id="${hostId}"]`).forEach((triggerEl) => {
            const isActive = triggerEl.getAttribute('data-pjx-panel-key') === activeKey;
            triggerEl.setAttribute('aria-selected', isActive ? 'true' : 'false');
            triggerEl.tabIndex = isActive ? 0 : -1;
        });
    }

    function pxPanelShowPanel(hostRoot, panelKey, trigger) {
        const hostId = hostRoot.id;
        if (!hostId) return;
        const target = hostRoot.querySelector(
            '.pjx-panel__panel[data-pjx-panel-key="' + panelKey + '"]'
        );
        if (!target) return;
        if (!target.hidden) return; // already active: nothing to announce
        const detail = { reason: 'trigger', trigger: trigger || null };
        if (!fire(target, 'pjx:before-reveal', detail, true)) return;
        hostRoot.querySelectorAll('.pjx-panel__panel').forEach((panelEl) => {
            if (panelEl !== target) {
                panelEl.hidden = true;
                panelEl.removeAttribute('data-pjx-revealed');
            }
        });
        target.hidden = false;
        target.setAttribute('data-pjx-revealed', '');
        pxPanelSyncTriggers(hostId, panelKey);
        fire(target, 'pjx:reveal', detail);
    }

    function pxPanelInit() {
        document.querySelectorAll('.pjx-panel').forEach((root) => {
            const hostId = root.id;
            if (!hostId) return;
            let activeKey = null;
            root.querySelectorAll('.pjx-panel__panel').forEach((panelEl) => {
                if (!panelEl.hidden) {
                    activeKey = panelEl.getAttribute('data-pjx-panel-key');
                }
            });
            if (activeKey === null) {
                const first = root.querySelector('.pjx-panel__panel');
                if (first) {
                    activeKey = first.getAttribute('data-pjx-panel-key');
                    first.removeAttribute('hidden');
                    root.querySelectorAll('.pjx-panel__panel').forEach((panelEl) => {
                        if (panelEl !== first) panelEl.hidden = true;
                    });
                }
            }
            if (activeKey !== null) {
                pxPanelSyncTriggers(hostId, activeKey);
                const visible = root.querySelector('.pjx-panel__panel:not([hidden])');
                if (visible && !visible.hasAttribute('data-pjx-revealed')) {
                    visible.setAttribute('data-pjx-revealed', '');
                    fire(visible, 'pjx:reveal', { reason: 'api', trigger: null });
                }
            }
        });
    }

    document.addEventListener('click', (e) => {
        const trigger = e.target.closest('.pjx-panel-trigger');
        if (!trigger) return;
        const hostId = trigger.getAttribute('data-pjx-panel-id');
        const panelKey = trigger.getAttribute('data-pjx-panel-key');
        if (!hostId || !panelKey) return;
        const hostRoot = document.getElementById(hostId);
        if (!hostRoot || !hostRoot.classList.contains('pjx-panel')) return;
        e.preventDefault();
        const targetPanel = hostRoot.querySelector(
            '.pjx-panel__panel[data-pjx-panel-key="' + panelKey + '"]'
        );
        if (!targetPanel) {
            console.warn('pjx-panel: no panel for key', panelKey, 'in', hostId);
            return;
        }
        pxPanelShowPanel(hostRoot, panelKey, trigger);
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
}());
