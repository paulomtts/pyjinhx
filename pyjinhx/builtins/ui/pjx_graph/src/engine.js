(function () {
  window.pjx = window.pjx || {};
  // Loading the asset twice must keep the first namespace, so state a page
  // already attached to it survives.
  if (!window.pjx.graph) {
    window.pjx.graph = {};
  }
  const graph = window.pjx.graph;
  // A second load keeps the first engine, so its instances stay reachable.
  if (graph.mount) {
    return;
  }

  const d3 = __pjxD3;
  const instances = new WeakMap();

  function part(parent, selector, direct) {
    // PJXGraph's own parts are direct children, so a nested graph never
    // satisfies them; the nodes slot may be wrapped by the app.
    const found = parent.querySelector(direct ? ':scope > ' + selector : selector);
    if (!found) {
      throw new Error('pjx.graph.mount: [data-pjx-graph] stage is missing ' + selector);
    }
    return found;
  }

  function paint(viewport, t) {
    viewport.style.transform = 'translate(' + t.x + 'px, ' + t.y + 'px) scale(' + t.k + ')';
  }

  function attachZoom(canvas, viewport) {
    const zoom = d3.zoom()
      .on('zoom', (event) => paint(viewport, event.transform));
    // Double-click stays free for selection; zoom is the wheel and the controls.
    d3.select(canvas).call(zoom).on('dblclick.zoom', null);
    d3.select(canvas).call(zoom.transform, d3.zoomIdentity);
  }

  function mount(root) {
    if (!(root instanceof Element) || !root.hasAttribute('data-pjx-graph')) {
      throw new Error('pjx.graph.mount: expected a [data-pjx-graph] element');
    }
    const existing = instances.get(root);
    if (existing) {
      return existing;
    }
    const canvas = part(root, '.pjx-graph__canvas', true);
    const viewport = part(canvas, '.pjx-graph__viewport', true);
    part(viewport, 'svg.pjx-graph__edge-plane', true);
    part(viewport, '.pjx-graph__nodes', false);
    attachZoom(canvas, viewport);
    const instance = { root: root };
    instances.set(root, instance);
    return instance;
  }

  function get(root) {
    return instances.get(root) || null;
  }

  function boot(subtree) {
    const stages = Array.from(subtree.querySelectorAll('[data-pjx-graph]'));
    if (subtree.matches && subtree.matches('[data-pjx-graph]')) {
      stages.unshift(subtree);
    }
    stages.forEach((stage) => {
      // One broken stage must not keep the others on the page from booting.
      try {
        mount(stage);
      } catch (error) {
        console.error(error);
      }
    });
  }

  function watch() {
    boot(document);
    // Observing only after the parser is done: a stage it is still streaming
    // is seen before its children exist and would fail to mount.
    new MutationObserver((mutations) => {
      mutations.forEach((m) => m.addedNodes.forEach((node) => {
        if (node.nodeType === 1) boot(node);
      }));
    }).observe(document.documentElement, { childList: true, subtree: true });
  }

  // Covers stages the observer never sees added, e.g. one that gained
  // data-pjx-graph or its parts after insertion.
  document.addEventListener('htmx:load', (event) => {
    if (event.target.querySelectorAll) boot(event.target);
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', watch);
  } else {
    watch();
  }

  graph.mount = mount;
  graph.get = get;
})();
