(function () {
    window.px = window.px || {};
    if (px.popover) return;

    function fire(el, name, detail, cancelable) {
        return el.dispatchEvent(new CustomEvent(name, {
            bubbles: true, cancelable: Boolean(cancelable), detail: detail || {},
        }));
    }

    function rootOf(panel) {
        return panel.closest('[data-px-popover]') || panel;
    }

    function triggerFor(panel) {
        const root = panel.closest('[data-px-popover]');
        return root ? root.querySelector('[data-px-toggle]') : null;
    }

    function resolvePanel(idOrEl) {
        if (typeof idOrEl === 'string') return document.getElementById(idOrEl);
        return idOrEl;
    }

    function open(idOrEl, reason, trigger) {
        const panel = resolvePanel(idOrEl);
        if (!panel || !panel.hidden) return false;
        const target = rootOf(panel);
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(target, 'px:popover:before-open', detail, true)) return false;
        panel.hidden = false;
        const t = trigger || triggerFor(panel);
        if (t) t.setAttribute('aria-expanded', 'true');
        fire(target, 'px:popover:open', detail);
        return true;
    }

    function close(idOrEl, reason, trigger) {
        const panel = resolvePanel(idOrEl);
        if (!panel || panel.hidden) return false;
        const target = rootOf(panel);
        const detail = { reason: reason || 'api', trigger: trigger || null };
        if (!fire(target, 'px:popover:before-close', detail, true)) return false;
        panel.hidden = true;
        const t = trigger || triggerFor(panel);
        if (t) t.setAttribute('aria-expanded', 'false');
        fire(target, 'px:popover:close', detail);
        return true;
    }

    function toggle(idOrEl, reason, trigger) {
        const panel = resolvePanel(idOrEl);
        if (!panel) return false;
        return panel.hidden ? open(panel, reason, trigger) : close(panel, reason, trigger);
    }

    function panelForToggle(toggleEl) {
        const explicit = toggleEl.getAttribute('data-px-toggle');
        if (explicit) return document.getElementById(explicit);
        const root = toggleEl.closest('[data-px-popover]');
        return root ? root.querySelector('[data-px-popover-panel]') : null;
    }

    document.addEventListener('click', (e) => {
        const closer = e.target.closest('[data-px-close]');
        if (closer) {
            const panel = closer.closest('[data-px-popover-panel]');
            if (panel) {
                close(panel, 'trigger', closer);
                return;
            }
        }
        const toggleEl = e.target.closest('[data-px-toggle]');
        const targetPanel = toggleEl ? panelForToggle(toggleEl) : null;
        // Close every open panel whose root doesn't contain the click —
        // also when clicking a trigger (so opening B closes A; nested popovers survive).
        document.querySelectorAll('[data-px-popover-panel]:not([hidden])').forEach((panel) => {
            if (panel === targetPanel) return;
            if (!rootOf(panel).contains(e.target)) close(panel, 'backdrop', null);
        });
        if (toggleEl && targetPanel) toggle(targetPanel, 'trigger', toggleEl);
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            const toggleEl = e.target.closest('div[data-px-toggle][role="button"]');
            if (toggleEl) {
                e.preventDefault();
                const panel = panelForToggle(toggleEl);
                if (panel) toggle(panel, 'trigger', toggleEl);
                return;
            }
        }
        if (e.key !== 'Escape') return;
        document.querySelectorAll('[data-px-popover-panel]:not([hidden])').forEach((panel) => {
            close(panel, 'escape', null);
        });
    });

    px.popover = { open: open, close: close, toggle: toggle };
}());
