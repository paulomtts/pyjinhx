(function () {
  window.pjx = window.pjx || {};
  // Loading the asset twice must keep the first namespace, so state a page
  // already attached to it survives.
  if (!window.pjx.graph) {
    window.pjx.graph = {};
  }
})();
