// Applies the region loading class. Lives next to pjx.js rather than under
// builtins/ui/ because it has no host element, no template and no descriptor:
// it ships unconditionally with the runtime, not through the lazy-asset door.
(function () {
  function targets(id) {
    var region = window.pjx && pjx.region(id);
    return region ? pjx.loadingTargets(region) : [];
  }

  document.addEventListener("pjx:region-loading-start", function (evt) {
    targets(evt.detail.id).forEach(function (t) {
      t.classList.add(pjx.loadingClass(t));
    });
  });

  document.addEventListener("pjx:region-loading-end", function (evt) {
    targets(evt.detail.id).forEach(function (t) {
      t.classList.remove(pjx.loadingClass(t));
    });
  });
})();
