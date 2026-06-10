(function () {
    window.px = window.px || {};
    if (px._panelWired) return;
    px._panelWired = true;

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function pxPanelSyncTriggers(hostId, activeKey) {
        document.querySelectorAll(`.px-panel-trigger[data-px-panel-id="${hostId}"]`).forEach((triggerEl) => {
            const isActive = triggerEl.getAttribute('data-px-panel-key') === activeKey;
            triggerEl.setAttribute('aria-selected', isActive ? 'true' : 'false');
            triggerEl.tabIndex = isActive ? 0 : -1;
        });
    }

    function pxPanelShowPanel(hostRoot, panelKey, trigger) {
        const hostId = hostRoot.id;
        if (!hostId) return;
        const target = hostRoot.querySelector(
            '.px-panel__panel[data-px-panel-key="' + panelKey + '"]'
        );
        if (!target) return;
        if (!target.hidden) return; // already active: nothing to announce
        const detail = { reason: 'trigger', trigger: trigger || null };
        if (!fire(target, 'px:before-reveal', detail, true)) return;
        hostRoot.querySelectorAll('.px-panel__panel').forEach((panelEl) => {
            if (panelEl !== target) {
                panelEl.hidden = true;
                panelEl.removeAttribute('data-px-revealed');
            }
        });
        target.hidden = false;
        target.setAttribute('data-px-revealed', '');
        pxPanelSyncTriggers(hostId, panelKey);
        fire(target, 'px:reveal', detail);
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
                const visible = root.querySelector('.px-panel__panel:not([hidden])');
                if (visible && !visible.hasAttribute('data-px-revealed')) {
                    visible.setAttribute('data-px-revealed', '');
                    fire(visible, 'px:reveal', { reason: 'api', trigger: null });
                }
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
