(function () {
  "use strict";
  window.pjx = window.pjx || {};
  if (pjx._accordionGroupWired) return;
  pjx._accordionGroupWired = true;

  function applyDefaultOpen(el) {
    var spec = el.dataset.defaultOpen;
    if (!spec || spec === "none") return;
    var items = el.querySelectorAll(":scope > details");
    if (spec === "first") {
      if (items.length) items[0].open = true;
    } else if (spec === "all") {
      items.forEach(function (d) { d.open = true; });
    }
  }

  function initGroup(el) {
    if (el.dataset.pjxGroupInit) return;
    el.dataset.pjxGroupInit = "1";

    applyDefaultOpen(el);

    if (el.dataset.mode !== "exclusive") return;
    el.addEventListener("toggle", function (e) {
      if (!e.target.matches("details") || !e.target.open) return;
      el.querySelectorAll("details[open]").forEach(function (d) {
        if (d !== e.target) d.removeAttribute("open");
      });
    }, true);
  }

  function init() {
    document
      .querySelectorAll("[data-pjx-accordion-group]")
      .forEach(initGroup);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  document.addEventListener("htmx:afterSettle", function (e) {
    var root = (e.detail && e.detail.elt) || document;
    if (root.querySelectorAll) {
      root.querySelectorAll("[data-pjx-accordion-group]").forEach(initGroup);
    }
  });
})();
