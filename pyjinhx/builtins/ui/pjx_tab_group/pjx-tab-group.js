(function () {
  window.pjx = window.pjx || {};
  var rootEl = document.documentElement;
  if (rootEl.dataset.pjxTabsBound) return;
  rootEl.dataset.pjxTabsBound = "1";
  var uid = 0;

  function fire(el, name, detail, cancelable) {
    return el.dispatchEvent(new CustomEvent(name, { bubbles: true, cancelable: !!cancelable, detail: detail || {} }));
  }
  function byId(id) { return id ? document.getElementById(id) : null; }
  function controlledPanel(tab) { return byId(tab.getAttribute("aria-controls")); }

  // A tab's group: its containing group, else the group of the panel it controls.
  function groupOf(el) {
    var g = el.closest("[data-pjx-tab-group]");
    if (g) return g;
    var panel = controlledPanel(el);
    return panel ? panel.closest("[data-pjx-tab-group]") : null;
  }
  function isListTab(tab) { return !!tab.closest('[role="tablist"]'); }

  // All tabs bound to this group (list tabs + detached triggers), document order.
  function tabsOf(group) {
    return Array.prototype.filter.call(
      document.querySelectorAll("[data-pjx-tab]"),
      function (t) { return groupOf(t) === group; }
    );
  }
  function panelsOf(group) {
    return Array.prototype.filter.call(
      group.querySelectorAll('[role="tabpanel"]'),
      function (p) { return p.closest("[data-pjx-tab-group]") === group; }
    );
  }
  // Tabs participating in roving focus: only those inside the same tablist.
  function listTabsOf(tablist) {
    return Array.prototype.filter.call(
      tablist.querySelectorAll("[data-pjx-tab]"),
      function (t) { return t.closest('[role="tablist"]') === tablist; }
    );
  }

  function setActiveState(tab, on) {
    tab.classList.toggle("pjx-tab--selected", on);
    if (isListTab(tab)) {
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
    } else if (on) {
      tab.setAttribute("aria-current", "true");
    } else {
      tab.removeAttribute("aria-current");
    }
  }

  function initGroup(group) {
    if (group.dataset.pjxTabsInit) return;
    group.dataset.pjxTabsInit = "1";
    if (!group.id) group.id = "pjx-tabs-" + (++uid);
    var tabs = tabsOf(group), panels = panelsOf(group);
    var explicit = {};
    tabs.forEach(function (t) { var c = t.getAttribute("aria-controls"); if (c) explicit[c] = true; });
    var queue = panels.filter(function (p) { return !(p.id && explicit[p.id]); });
    var qi = 0;
    tabs.forEach(function (tab, i) {
      if (!tab.id) tab.id = group.id + "-tab-" + i;
      var panel = controlledPanel(tab);
      if (!panel) panel = queue[qi++] || null;
      if (panel) {
        if (!panel.id) panel.id = group.id + "-panel-" + i;
        tab.setAttribute("aria-controls", panel.id);
        if (!panel.getAttribute("aria-labelledby")) panel.setAttribute("aria-labelledby", tab.id);
      }
      // Detached triggers can't carry role="tab" (invalid outside a tablist):
      // downgrade to button semantics; list tabs keep their server-rendered roles.
      if (!isListTab(tab)) {
        tab.setAttribute("role", "button");
        tab.tabIndex = 0;
        tab.removeAttribute("aria-selected");
      }
    });
    var selected = tabs.filter(function (t) { return t.classList.contains("pjx-tab--selected"); })[0] || tabs[0];
    if (selected) select(group, selected, { reason: "api", trigger: null }, true);
    initReorder(group);
  }

  function reorderableTablists(group) {
    return Array.prototype.filter.call(
      group.querySelectorAll('[role="tablist"][data-pjx-tab-reorderable]'),
      function (tl) { return tl.closest("[data-pjx-tab-group]") === group; }
    );
  }

  function initReorder(group) {
    reorderableTablists(group).forEach(function (tablist) {
      listTabsOf(tablist).forEach(function (tab) {
        if (tab.getAttribute("data-pjx-tab-pinned") == null) tab.draggable = true;
      });
    });
  }

  // Moves `tab` to `toIndex` among its tablist's list tabs, firing the
  // cancelable pjx:tab:before-reorder / pjx:tab:reorder pair either way (drag
  // or keyboard) drives it through.
  function moveTab(group, tablist, tab, toIndex) {
    var tabs = listTabsOf(tablist), fromIndex = tabs.indexOf(tab);
    if (fromIndex < 0 || toIndex < 0 || toIndex >= tabs.length || toIndex === fromIndex) return;
    var detail = { id: tab.id, from: fromIndex, to: toIndex };
    if (!fire(group, "pjx:tab:before-reorder", detail, true)) return;
    var ref = tabs[toIndex];
    tablist.insertBefore(tab, fromIndex < toIndex ? ref.nextSibling : ref);
    fire(group, "pjx:tab:reorder", detail);
  }

  var dragTab = null;
  document.addEventListener("dragstart", function (e) {
    var tab = e.target.closest && e.target.closest("[draggable='true'][data-pjx-tab]");
    if (!tab) return;
    dragTab = tab;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", tab.id);
  });
  document.addEventListener("dragover", function (e) {
    if (!dragTab) return;
    var tablist = dragTab.closest('[role="tablist"][data-pjx-tab-reorderable]');
    if (tablist && tablist.contains(e.target)) e.preventDefault();
  });
  document.addEventListener("drop", function (e) {
    if (!dragTab) return;
    var tablist = dragTab.closest('[role="tablist"][data-pjx-tab-reorderable]');
    var over = tablist && e.target.closest("[data-pjx-tab]");
    if (tablist && over && over !== dragTab && tablist.contains(over)) {
      e.preventDefault();
      var group = groupOf(dragTab);
      if (group) moveTab(group, tablist, dragTab, listTabsOf(tablist).indexOf(over));
    }
  });
  document.addEventListener("dragend", function () { dragTab = null; });

  function select(group, tab, detail, silent) {
    var panel = controlledPanel(tab);
    if (panel && !silent && !fire(panel, "pjx:before-reveal", detail, true)) return false;
    tabsOf(group).forEach(function (t) { setActiveState(t, t === tab); });
    panelsOf(group).forEach(function (p) {
      var on = p === panel;
      p.hidden = !on;
      if (!on) p.removeAttribute("data-pjx-revealed");
    });
    if (panel) { panel.setAttribute("data-pjx-revealed", ""); fire(panel, "pjx:reveal", detail); }
    return true;
  }

  function closeTab(group, tab) {
    if (tab.getAttribute("data-pjx-tab-pinned") != null) return;
    if (!fire(group, "pjx:tab:close", { id: tab.id, tab: tab }, true)) return;
    var tabs = tabsOf(group), idx = tabs.indexOf(tab), panel = controlledPanel(tab);
    var wasSelected = tab.classList.contains("pjx-tab--selected");
    var nb = tabs[idx + 1] || tabs[idx - 1] || null;
    var id = tab.id;
    if (panel && panel.parentNode) panel.parentNode.removeChild(panel);
    if (tab.parentNode) tab.parentNode.removeChild(tab);
    if (nb && wasSelected) { select(group, nb, { reason: "close", trigger: null }); nb.focus(); }
    fire(group, "pjx:tab:closed", { id: id });
  }

  document.addEventListener("click", function (e) {
    var closeBtn = e.target.closest("[data-pjx-tab-close]");
    if (closeBtn) {
      var t0 = closeBtn.closest("[data-pjx-tab]"), g0 = t0 && groupOf(t0);
      if (g0 && t0) { e.preventDefault(); closeTab(g0, t0); }
      return;
    }
    var tab = e.target.closest("[data-pjx-tab]");
    if (!tab) return;
    var group = groupOf(tab);
    if (!group) return;
    e.preventDefault();
    if (!tab.classList.contains("pjx-tab--selected")) select(group, tab, { reason: "trigger", trigger: tab });
  });

  document.addEventListener("keydown", function (e) {
    var tab = e.target.closest && e.target.closest("[data-pjx-tab]");
    if (!tab) return;
    var group = groupOf(tab);
    if (!group) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (!tab.classList.contains("pjx-tab--selected")) select(group, tab, { reason: "trigger", trigger: tab });
      return;
    }
    if (e.key === "Delete" || e.key === "Backspace") {
      if (tab.classList.contains("pjx-tab--closeable")) { e.preventDefault(); closeTab(group, tab); }
      return;
    }
    // Arrow roving only within a tablist; standalone triggers don't rove.
    var tablist = tab.closest('[role="tablist"]');
    if (!tablist) return;
    if (e.ctrlKey && tablist.hasAttribute("data-pjx-tab-reorderable") &&
        (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
      e.preventDefault();
      var idx0 = listTabsOf(tablist).indexOf(tab);
      moveTab(group, tablist, tab, idx0 + (e.key === "ArrowRight" ? 1 : -1));
      tab.focus();
      return;
    }
    var tabs = listTabsOf(tablist), idx = tabs.indexOf(tab), next = null;
    if (e.key === "ArrowRight") next = tabs[(idx + 1) % tabs.length];
    else if (e.key === "ArrowLeft") next = tabs[(idx - 1 + tabs.length) % tabs.length];
    else if (e.key === "Home") next = tabs[0];
    else if (e.key === "End") next = tabs[tabs.length - 1];
    else return;
    if (next) { e.preventDefault(); tab.tabIndex = -1; next.tabIndex = 0; next.focus(); }
  });

  function initAll(scope) {
    (scope && scope.querySelectorAll ? scope : document)
      .querySelectorAll("[data-pjx-tab-group]").forEach(initGroup);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { initAll(document); });
  } else { initAll(document); }
  document.addEventListener("htmx:afterSettle", function (e) { initAll((e.detail && e.detail.elt) || document); });
}());
