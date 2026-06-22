(function () {
  window.pjx = window.pjx || {};
  var root = document.documentElement;
  if (root.dataset.pjxResizableBound) return;
  root.dataset.pjxResizableBound = "1";

  function isPanel(el) { return el && el.matches && el.matches("[data-pjx-resizable-panel]"); }
  function panels(group) {
    return Array.prototype.filter.call(group.children, isPanel);
  }
  function groupOf(handle) {
    var g = handle.parentElement;
    return g && g.matches("[data-pjx-resizable-group]") ? g : null;
  }
  function num(el, attr, dflt) {
    var v = parseFloat(el.getAttribute(attr));
    return isNaN(v) ? dflt : v;
  }
  // A bound counts as a percentage ONLY if it is a bare number; "120px"/"content"
  // impose no percentage bound (the CSS floor + reconciliation own them).
  function pctBound(el, attr, dflt) {
    var raw = el.getAttribute(attr);
    if (raw == null || !/^[\d.]+$/.test(raw)) return dflt;
    return parseFloat(raw);
  }
  function mainSize(p, horiz) {
    var r = p.getBoundingClientRect();
    return horiz ? r.width : r.height;
  }
  // Redistribute the dragged pair's grow weights in proportion to their rendered
  // main-axis sizes, so the JS model matches the CSS-enforced floor exactly.
  function reconcile(nb, horiz) {
    var total = grow(nb.prev) + grow(nb.next);
    var ppx = mainSize(nb.prev, horiz), npx = mainSize(nb.next, horiz);
    var denom = ppx + npx;
    if (denom > 0) {
      nb.prev.style.flexGrow = String(total * ppx / denom);
      nb.next.style.flexGrow = String(total * npx / denom);
    }
  }
  function horizontal(group) { return group.dataset.direction !== "column"; }
  function grow(p) { return parseFloat(p.style.flexGrow) || 0; }
  function sizesOf(group) { return panels(group).map(grow); }

  function emit(group) {
    group.dispatchEvent(new CustomEvent("pjx:resize", {
      bubbles: true, detail: { sizes: sizesOf(group) },
    }));
  }

  function neighbors(handle) {
    var prev = handle.previousElementSibling;
    while (prev && !isPanel(prev)) prev = prev.previousElementSibling;
    var next = handle.nextElementSibling;
    while (next && !isPanel(next)) next = next.nextElementSibling;
    if (!isPanel(prev) || !isPanel(next)) return null;
    return { prev: prev, next: next };
  }

  // Move the boundary so the previous panel becomes `prevTarget` (% of the pair),
  // clamped by the percentage bounds, then reconciled to the CSS-enforced render.
  function apply(group, handle, nb, prevTarget) {
    var total = grow(nb.prev) + grow(nb.next);
    var lo = Math.max(pctBound(nb.prev, "data-min", 0), total - pctBound(nb.next, "data-max", 100));
    var hi = Math.min(pctBound(nb.prev, "data-max", 100), total - pctBound(nb.next, "data-min", 0));
    var prev = Math.min(hi, Math.max(lo, prevTarget));
    nb.prev.style.flexGrow = String(prev);
    nb.next.style.flexGrow = String(total - prev);
    reconcile(nb, horizontal(group));
    handle.setAttribute("aria-valuenow", String(Math.round(grow(nb.prev))));
  }

  function initGroup(group) {
    if (group.dataset.pjxResizableInit) return;
    group.dataset.pjxResizableInit = "1";
    var ps = panels(group);
    var total = ps.reduce(function (s, p) {
      return s + (num(p, "data-size", grow(p) || 1));
    }, 0) || 1;
    ps.forEach(function (p) {
      p.style.flexGrow = String(num(p, "data-size", grow(p) || 1) / total * 100);
    });
    Array.prototype.forEach.call(
      group.querySelectorAll(":scope > [data-pjx-resizable-handle]"),
      function (h) {
        h.setAttribute("aria-orientation", horizontal(group) ? "vertical" : "horizontal");
        var nb = neighbors(h);
        if (nb) {
          reconcile(nb, horizontal(group));
          h.setAttribute("aria-valuenow", String(Math.round(grow(nb.prev))));
        }
      }
    );
  }

  // ---- pointer drag ----
  var active = null;
  function axisPos(group, e) {
    var pt = e.touches && e.touches.length ? e.touches[0] : e;
    return horizontal(group) ? pt.clientX : pt.clientY;
  }
  function groupPx(group) {
    var r = group.getBoundingClientRect();
    return horizontal(group) ? r.width : r.height;
  }
  function start(e) {
    var handle = e.target.closest && e.target.closest("[data-pjx-resizable-handle]");
    if (!handle) return;
    var group = groupOf(handle), nb = group && neighbors(handle);
    if (!nb) return;
    e.preventDefault();
    reconcile(nb, horizontal(group));
    active = {
      group: group, handle: handle, nb: nb,
      startPos: axisPos(group, e), startPrev: grow(nb.prev), px: groupPx(group) || 1,
    };
    group.classList.add("pjx-resizable-group--dragging");
  }
  function move(e) {
    if (!active) return;
    e.preventDefault();
    var deltaPct = (axisPos(active.group, e) - active.startPos) / active.px * 100;
    apply(active.group, active.handle, active.nb, active.startPrev + deltaPct);
  }
  function end() {
    if (!active) return;
    active.group.classList.remove("pjx-resizable-group--dragging");
    emit(active.group);
    active = null;
  }
  document.addEventListener("mousedown", start);
  document.addEventListener("mousemove", move);
  document.addEventListener("mouseup", end);
  document.addEventListener("touchstart", start, { passive: false });
  document.addEventListener("touchmove", move, { passive: false });
  document.addEventListener("touchend", end);

  // ---- keyboard ----
  var STEP = 5;
  document.addEventListener("keydown", function (e) {
    var handle = e.target.closest && e.target.closest("[data-pjx-resizable-handle]");
    if (!handle) return;
    var group = groupOf(handle), nb = group && neighbors(handle);
    if (!nb) return;
    reconcile(nb, horizontal(group));
    var h = horizontal(group), cur = grow(nb.prev), total = cur + grow(nb.next), target = null;
    if ((h && e.key === "ArrowLeft") || (!h && e.key === "ArrowUp")) target = cur - STEP;
    else if ((h && e.key === "ArrowRight") || (!h && e.key === "ArrowDown")) target = cur + STEP;
    else if (e.key === "Home") target = 0;
    else if (e.key === "End") target = total;
    if (target === null) return;
    e.preventDefault();
    apply(group, handle, nb, target);
    emit(group);
  });

  // ---- init ----
  function initAll(scope) {
    (scope && scope.querySelectorAll ? scope : document)
      .querySelectorAll("[data-pjx-resizable-group]").forEach(initGroup);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { initAll(document); });
  } else {
    initAll(document);
  }
  document.addEventListener("htmx:afterSettle", function (e) {
    initAll((e.detail && e.detail.elt) || document);
  });
})();
