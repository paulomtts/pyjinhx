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
  // Room left around the nodes when a fit frames them.
  const FIT_PAD = 48;

  function part(parent, selector, direct) {
    // PJXGraph's own parts are direct children, so a nested graph never
    // satisfies them; the nodes slot may be wrapped by the app.
    const found = parent.querySelector(direct ? ':scope > ' + selector : selector);
    if (!found) {
      throw new Error('pjx.graph.mount: [data-pjx-graph] stage is missing ' + selector);
    }
    return found;
  }

  function scaleBound(root, name, fallback) {
    const raw = root.getAttribute('data-pjx-graph-scale-' + name);
    return raw === null ? fallback : Number(raw);
  }

  function scaleExtent(root) {
    const min = scaleBound(root, 'min', 0.2);
    const max = scaleBound(root, 'max', 2);
    // NaN fails every comparison, so a non-numeric attribute lands here too.
    if (!(min > 0 && min <= max && Number.isFinite(max))) {
      throw new Error('pjx.graph.mount: invalid scale range ' + min + '..' + max);
    }
    return [min, max];
  }

  // A press pans only from empty canvas: nodes, ports and edges will have
  // their own drags, and controls outside the viewport are buttons.
  function isBackground(target, canvas, viewport) {
    if (target === canvas) return true;
    if (!viewport.contains(target) || target.closest('[data-node-id]')) return false;
    const plane = target.closest('svg.pjx-graph__edge-plane');
    return !plane || plane === target;
  }

  function paint(viewport, t) {
    viewport.style.transform = 'translate(' + t.x + 'px, ' + t.y + 'px) scale(' + t.k + ')';
  }

  // Storage can throw anywhere, even on reading window.localStorage, and a
  // broken store must never break pan/zoom.
  function readRecord(key) {
    try {
      const value = JSON.parse(window.localStorage.getItem(key));
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch (error) {
      return {};
    }
  }

  function saveView(key, t) {
    // Other fields of the record belong to other features and are kept.
    const record = readRecord(key);
    record.view = { x: t.x, y: t.y, k: t.k };
    try {
      window.localStorage.setItem(key, JSON.stringify(record));
    } catch (error) {
      // Pan/zoom keeps working, just without persistence.
    }
  }

  function clampScale(k, extent) {
    return Math.min(extent[1], Math.max(extent[0], k));
  }

  // null, not identity, for an unusable view: only a usable one stops the fit.
  function storedView(record, extent) {
    const view = record.view;
    if (!view || !Number.isFinite(view.x) || !Number.isFinite(view.y)
        || !Number.isFinite(view.k) || view.k <= 0) {
      return null;
    }
    // A view saved under a wider range is pulled into the current one.
    return d3.zoomIdentity.translate(view.x, view.y).scale(clampScale(view.k, extent));
  }

  function attachZoom(root, canvas, viewport) {
    const extent = scaleExtent(root);
    const storageKey = root.getAttribute('data-pjx-graph-storage-key');
    const key = storageKey ? 'pjx-graph:' + storageKey : null;
    const zoom = d3.zoom()
      .scaleExtent(extent)
      // Wheel zooms from anywhere over the canvas; only presses need background.
      .filter((event) => event.type === 'wheel'
        || (!event.ctrlKey && !event.button && isBackground(event.target, canvas, viewport)))
      .on('zoom', (event) => paint(viewport, event.transform));
    // Double-click stays free for selection; zoom is the wheel and the controls.
    d3.select(canvas).call(zoom).on('dblclick.zoom', null);
    // d3 lets a wheel at either end of the range scroll the page.
    canvas.addEventListener('wheel', (event) => event.preventDefault(), { passive: false });
    const restored = key ? storedView(readRecord(key), extent) : null;
    d3.select(canvas).call(zoom.transform, restored || d3.zoomIdentity);
    return { zoom: zoom, extent: extent, key: key, restored: restored !== null };
  }

  // Listening only now, so the initial view is never written back.
  function settle(root, canvas, view) {
    if (view.key) view.zoom.on('end', () => saveView(view.key, d3.zoomTransform(canvas)));
    root.setAttribute('data-pjx-graph-ready', '');
  }

  // A graph nested inside a node owns its own nodes.
  function nodesOf(root, viewport) {
    return Array.from(viewport.querySelectorAll('[data-node-id]'))
      .filter((node) => node.closest('[data-pjx-graph]') === root);
  }

  function coordinate(node, axis) {
    const raw = node.getAttribute('data-' + axis);
    // Number() reads a missing or blank attribute as 0, a position nobody wrote.
    const value = raw === null || raw.trim() === '' ? NaN : Number(raw);
    return Number.isFinite(value) ? value : null;
  }

  // data-x/y are the server's truth; an inline style can be stale, e.g. after
  // a partial swap kept an old node.
  function place(node) {
    ['x', 'y'].forEach((axis) => {
      const value = coordinate(node, axis);
      if (value !== null) node.style.setProperty('--pjx-graph-node-' + axis, value + 'px');
    });
  }

  // A stage inserted mid-layout reports a size that is about to change, so
  // wait until it holds for a frame; a hidden stage never gets one, so give up
  // after ten tries.
  function whenLaidOut(canvas, done) {
    let attempts = 0;
    (function check() {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      requestAnimationFrame(() => {
        attempts += 1;
        const settled = width > 0 && height > 0
          && width === canvas.clientWidth && height === canvas.clientHeight;
        if (settled || attempts === 10) done(); else check();
      });
    })();
  }

  function createInstance(root, canvas, viewport, view) {
    // World coordinates are the viewport's untransformed pixels, the space
    // data-x/y are written in, so they do not change with pan/zoom.
    function toWorld(clientX, clientY) {
      const origin = viewport.getBoundingClientRect();
      const k = d3.zoomTransform(canvas).k;
      return { x: (clientX - origin.left) / k, y: (clientY - origin.top) / k };
    }

    // Compared as strings, so ids need no CSS escaping.
    function findNode(id) {
      return nodesOf(root, viewport)
        .find((node) => node.getAttribute('data-node-id') === id) || null;
    }

    function boxOf(node) {
      const rect = node.getBoundingClientRect();
      const at = toWorld(rect.left, rect.top);
      return { x: at.x, y: at.y, width: node.offsetWidth, height: node.offsetHeight };
    }

    function box(id) {
      const node = findNode(id);
      return node && boxOf(node);
    }

    function inAnchor(id) {
      const b = box(id);
      return b && { x: b.x, y: b.y + b.height / 2 };
    }

    function outAnchor(id, port) {
      const node = findNode(id);
      if (!node) return null;
      const dot = Array.from(node.querySelectorAll('[data-pjx-graph-port="out"]'))
        // A graph nested in the node may have a port with the same key.
        .find((el) => el.getAttribute('data-port') === port && el.closest('[data-node-id]') === node);
      if (!dot) {
        const b = boxOf(node);
        return { x: b.x + b.width, y: b.y + b.height / 2 };
      }
      // The ports straddle the edge with a transform, which offsetLeft ignores.
      const rect = dot.getBoundingClientRect();
      return toWorld(rect.left + rect.width / 2, rect.top + rect.height / 2);
    }

    function fit() {
      // A hidden node has no box; its zero rect would pull the frame to the origin.
      const boxes = nodesOf(root, viewport)
        .filter((node) => node.getClientRects().length > 0)
        .map(boxOf);
      if (!boxes.length) return;
      const left = Math.min(...boxes.map((b) => b.x));
      const top = Math.min(...boxes.map((b) => b.y));
      const right = Math.max(...boxes.map((b) => b.x + b.width));
      const bottom = Math.max(...boxes.map((b) => b.y + b.height));
      // Client sizes leave out the canvas border.
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const k = clampScale(Math.min(
        Math.max(1, width - 2 * FIT_PAD) / Math.max(1, right - left),
        Math.max(1, height - 2 * FIT_PAD) / Math.max(1, bottom - top)), view.extent);
      const t = d3.zoomIdentity
        .translate(width / 2 - k * (left + right) / 2, height / 2 - k * (top + bottom) / 2)
        .scale(k);
      d3.select(canvas).call(view.zoom.transform, t);
    }

    return { root: root, box: box, inAnchor: inAnchor, outAnchor: outAnchor, fit: fit };
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
    const view = attachZoom(root, canvas, viewport);
    nodesOf(root, viewport).forEach(place);
    const instance = createInstance(root, canvas, viewport, view);
    instances.set(root, instance);
    // A restored view is where the user left off; only a fresh stage is framed.
    if (view.restored) {
      settle(root, canvas, view);
    } else {
      whenLaidOut(canvas, () => {
        instance.fit();
        settle(root, canvas, view);
      });
    }
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
