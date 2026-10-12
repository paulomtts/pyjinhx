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
    const instance = { root: root };
    instances.set(root, instance);
    return instance;
  }

  function get(root) {
    return instances.get(root) || null;
  }

  graph.mount = mount;
  graph.get = get;
})();
