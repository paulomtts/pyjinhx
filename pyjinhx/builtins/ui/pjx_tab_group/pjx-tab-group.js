(function () {
  window.pjx = window.pjx || {};
  var rootEl = document.documentElement;
  if (rootEl.dataset.pjxTabsBound) return;
  rootEl.dataset.pjxTabsBound = "1";
  var uid = 0;

  function fire(el, name, detail, cancelable) {
    return el.dispatchEvent(new CustomEvent(name, { bubbles: true, cancelable: !!cancelable, detail: detail || {} }));
  }
  function groupOf(el) { return el.closest("[data-pjx-tab-group]"); }
  function inGroup(group) { return function (el) { return groupOf(el) === group; }; }
  function tabsOf(group) {
    return Array.prototype.filter.call(group.querySelectorAll('[role="tab"]'), inGroup(group));
  }
  function panelsOf(group) {
    return Array.prototype.filter.call(group.querySelectorAll('[role="tabpanel"]'), inGroup(group));
  }
  function panelFor(group, tab) {
    var id = tab.getAttribute("aria-controls");
    return id ? group.querySelector("#" + (window.CSS && CSS.escape ? CSS.escape(id) : id)) : null;
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
      var panel = panelFor(group, tab);
      if (!panel) panel = queue[qi++] || null;
      if (panel) {
        if (!panel.id) panel.id = group.id + "-panel-" + i;
        tab.setAttribute("aria-controls", panel.id);
        if (!panel.getAttribute("aria-labelledby")) panel.setAttribute("aria-labelledby", tab.id);
      }
    });
    var selected = tabs.filter(function (t) { return t.getAttribute("aria-selected") === "true"; })[0] || tabs[0];
    if (selected) select(group, selected, { reason: "api", trigger: null }, true);
  }

  function select(group, tab, detail, silent) {
    var panel = panelFor(group, tab);
    if (panel && !silent && !fire(panel, "pjx:before-reveal", detail, true)) return false;
    tabsOf(group).forEach(function (t) {
      var on = t === tab;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      t.classList.toggle("pjx-tab--selected", on);
    });
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
    var tabs = tabsOf(group), idx = tabs.indexOf(tab), panel = panelFor(group, tab);
    var wasSelected = tab.getAttribute("aria-selected") === "true";
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
      var g = groupOf(closeBtn), t = closeBtn.closest('[role="tab"]');
      if (g && t) { e.preventDefault(); closeTab(g, t); }
      return;
    }
    var tab = e.target.closest('[role="tab"]');
    if (!tab) return;
    var group = groupOf(tab);
    if (!group) return;
    e.preventDefault();
    if (tab.getAttribute("aria-selected") !== "true") select(group, tab, { reason: "trigger", trigger: tab });
  });

  document.addEventListener("keydown", function (e) {
    var tab = e.target.closest && e.target.closest('[role="tab"]');
    if (!tab) return;
    var group = groupOf(tab);
    if (!group) return;
    var tabs = tabsOf(group), idx = tabs.indexOf(tab), next = null;
    if (e.key === "ArrowRight") next = tabs[(idx + 1) % tabs.length];
    else if (e.key === "ArrowLeft") next = tabs[(idx - 1 + tabs.length) % tabs.length];
    else if (e.key === "Home") next = tabs[0];
    else if (e.key === "End") next = tabs[tabs.length - 1];
    else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (tab.getAttribute("aria-selected") !== "true") select(group, tab, { reason: "trigger", trigger: tab });
      return;
    } else if (e.key === "Delete" || e.key === "Backspace") {
      if (tab.classList.contains("pjx-tab--closeable")) { e.preventDefault(); closeTab(group, tab); }
      return;
    } else return;
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
