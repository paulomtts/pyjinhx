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
  // Aborted when a stage is dropped: everything the stage started outside
  // its own elements listens to it, so one abort stops all of it.
  const lives = new WeakMap();
  // Room left around the nodes when a fit frames them.
  const FIT_PAD = 48;
  // A press that moves no further than this, in screen pixels, is a click.
  const DRAG_SLOP = 4;
  // Pressing these inside a node uses them; it never drags the node.
  const INTERACTIVE = 'input, textarea, select, button, a[href], [contenteditable]';

  // One control step; two steps double or halve the scale.
  const ZOOM_STEP = Math.SQRT2;
  const SVG_NS = 'http://www.w3.org/2000/svg';
  // Gives each mounted stage its own path-id prefix, so ids never collide
  // across stages, whatever edge ids the app reuses.
  let stageCount = 0;

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

  // Delegated, so controls swapped in later work without rebinding. A
  // control in a nested stage belongs to that stage's own listener, and the
  // values are matched one by one so a name like "constructor" is no step.
  function listenForControls(root, canvas, instance) {
    canvas.addEventListener('click', (event) => {
      const control = event.target.closest('[data-pjx-graph-zoom], [data-pjx-graph-fit]');
      if (!control || !canvas.contains(control)
          || control.closest('[data-pjx-graph]') !== root) return;
      if (control.hasAttribute('data-pjx-graph-fit')) {
        instance.fit();
        return;
      }
      const value = control.getAttribute('data-pjx-graph-zoom');
      if (value === 'in') instance.zoomBy(1);
      else if (value === 'out') instance.zoomBy(-1);
    });
  }

  // Delegated, like the controls. A click is judged by its nearest node
  // inside this viewport: a node of a nested stage is left to that stage,
  // while the nested stage's own background still lies inside one of ours.
  function listenForSelection(root, canvas, viewport, plane, choose, deselect) {
    canvas.addEventListener('click', (event) => {
      const target = event.target;
      const node = target.closest('[data-node-id]');
      if (node && viewport.contains(node)) {
        if (node.closest('[data-pjx-graph]') === root) {
          choose('node', node.getAttribute('data-node-id'));
        }
        return;
      }
      if (target.parentNode === plane && target.classList.contains('pjx-graph__edge-hit')) {
        // An empty id cannot be named in an event, so its edge is not selectable.
        const id = target.getAttribute('data-edge-id');
        if (id) choose('edge', id);
        return;
      }
      if (isBackground(target, canvas, viewport)) deselect();
    });
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

  function writeRecord(key, record) {
    try {
      window.localStorage.setItem(key, JSON.stringify(record));
    } catch (error) {
      // The stage keeps working, just without persistence.
    }
  }

  function saveView(key, t) {
    // Other fields of the record belong to other features and are kept.
    const record = readRecord(key);
    record.view = { x: t.x, y: t.y, k: t.k };
    writeRecord(key, record);
  }

  // Ids are the app's strings, so "__proto__" or "constructor" must be read
  // as plain keys, never found on a prototype.
  function own(object, name) {
    return Object.prototype.hasOwnProperty.call(object, name);
  }

  function overridesOf(record) {
    const nodes = record.nodes;
    return nodes && typeof nodes === 'object' && !Array.isArray(nodes) ? nodes : null;
  }

  function usableOverride(o) {
    return o !== null && typeof o === 'object' && Number.isFinite(o.x) && Number.isFinite(o.y)
      && o.base !== null && typeof o.base === 'object'
      && Number.isFinite(o.base.x) && Number.isFinite(o.base.y);
  }

  function saveOverride(key, id, override) {
    const record = readRecord(key);
    const nodes = overridesOf(record) || {};
    // defineProperty, since assigning to "__proto__" would set the prototype.
    Object.defineProperty(nodes, id,
      { value: override, enumerable: true, writable: true, configurable: true });
    record.nodes = nodes;
    writeRecord(key, record);
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

  // A graph nested inside a node draws its own edges.
  function edgesOf(root, viewport) {
    return Array.from(viewport.querySelectorAll('[data-pjx-graph-edge]'))
      .filter((edge) => edge.closest('[data-pjx-graph]') === root);
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

  function moveTo(node, x, y) {
    node.style.setProperty('--pjx-graph-node-x', x + 'px');
    node.style.setProperty('--pjx-graph-node-y', y + 'px');
  }

  // A drop holds while the server still sends the position it was made
  // from. Once the server moves the node, the server wins and the drop is
  // forgotten, so a later return to the old spot cannot bring it back.
  function placeAll(nodes, key) {
    const record = key ? readRecord(key) : {};
    const overrides = overridesOf(record);
    let discarded = false;
    nodes.forEach((node) => {
      place(node);
      const id = node.getAttribute('data-node-id');
      if (!overrides || !own(overrides, id)) return;
      const o = overrides[id];
      if (usableOverride(o) && o.base.x === coordinate(node, 'x')
          && o.base.y === coordinate(node, 'y')) {
        moveTo(node, o.x, o.y);
      } else {
        delete overrides[id];
        discarded = true;
      }
    });
    if (discarded) writeRecord(key, record);
  }

  // A missing attribute reads as empty, as PJXGraphEdges would have written it.
  function attr(el, name) {
    return el.getAttribute(name) || '';
  }

  function svg(tag, attrs) {
    const el = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs).forEach((name) => el.setAttribute(name, attrs[name]));
    return el;
  }

  // A horizontal bezier between the anchors. The offset moves only the two
  // control points along the normal, so parallel edges bow apart while their
  // ends stay on the ports.
  function edgePath(p1, p2, offset) {
    const dx = Math.max(48, Math.abs(p2.x - p1.x) * 0.5);
    const len = Math.hypot(p2.x - p1.x, p2.y - p1.y) || 1;
    const nx = -(p2.y - p1.y) / len * offset;
    const ny = (p2.x - p1.x) / len * offset;
    return 'M ' + p1.x + ' ' + p1.y
      + ' C ' + (p1.x + dx + nx) + ' ' + (p1.y + ny)
      + ', ' + (p2.x - dx + nx) + ' ' + (p2.y + ny)
      + ', ' + p2.x + ' ' + p2.y;
  }

  // Parallel edges between two nodes spread this far apart.
  const FAN_GAP = 26;

  // Centred on zero, so the middle of an odd fan is a plain edge.
  function fanOffset(index, total) {
    return total < 2 ? 0 : (index - (total - 1) / 2) * FAN_GAP;
  }

  // Unordered, so A→B and B→A fan together; JSON keeps any id unambiguous.
  function pairOf(edge) {
    return JSON.stringify([edge.getAttribute('data-from'), edge.getAttribute('data-to')].sort());
  }

  // A stage inserted mid-layout reports a size that is about to change, so
  // wait until it holds for a frame; a hidden stage never gets one, so give up
  // after ten tries.
  function whenLaidOut(canvas, signal, done) {
    let attempts = 0;
    (function check() {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      requestAnimationFrame(() => {
        // A dropped stage never lays out, and its root must not turn ready.
        if (signal.aborted) return;
        attempts += 1;
        const settled = width > 0 && height > 0
          && width === canvas.clientWidth && height === canvas.clientHeight;
        if (settled || attempts === 10) done(); else check();
      });
    })();
  }

  function createInstance(root, canvas, viewport, plane, view, signal) {
    const prefix = 'pjx-graph-edge-' + (++stageCount) + '-';
    // Only the last pass's own elements are cleared, so anything else in the
    // plane survives a redraw.
    let drawn = [];
    // At most one selection, a node or an edge. Kind and id are kept
    // together, so a node and an edge sharing an id are different selections.
    let selected = null;

    // The first of several nodes sharing an id is the one findNode picks.
    function indexNodes() {
      const index = new Map();
      nodesOf(root, viewport).forEach((node) => {
        const id = node.getAttribute('data-node-id');
        if (!index.has(id)) index.set(id, node);
      });
      return index;
    }

    // The raw data-x/y each node was last placed with. Only a node whose
    // pair differs is placed: a swapped-in element has none yet, while
    // placing a kept node the server did not move would snap a drop the
    // user just made without a storage key back to the server position.
    const placedWith = new WeakMap();

    function serverPosition(node) {
      return JSON.stringify([node.getAttribute('data-x'), node.getAttribute('data-y')]);
    }

    function placeChanged() {
      const changed = nodesOf(root, viewport)
        .filter((node) => placedWith.get(node) !== serverPosition(node));
      placeAll(changed, view.key);
      changed.forEach((node) => placedWith.set(node, serverPosition(node)));
    }

    // Before the edges and any fit, so both see where the nodes show.
    placeChanged();

    // Every edge is redrawn on each reconcile: that keeps every pair's fan
    // correct and is cheap. At 200 edges over 50 nodes a redraw cost about
    // 15 ms, 12.6 ms of it finding nodes rather than drawing, so a redraw
    // indexes the nodes once and findNode reads that index while it runs.
    let index = null;

    // World coordinates are the viewport's untransformed pixels, the space
    // data-x/y are written in, so they do not change with pan/zoom.
    function toWorld(clientX, clientY) {
      const origin = viewport.getBoundingClientRect();
      const k = d3.zoomTransform(canvas).k;
      return { x: (clientX - origin.left) / k, y: (clientY - origin.top) / k };
    }

    // Compared as strings, so ids need no CSS escaping. Outside a redraw the
    // DOM is read live, so a node the app has just added is found at once.
    function findNode(id) {
      if (index) return index.get(id) || null;
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

    // About the canvas centre, so what sits in the middle of the view stays
    // there. Through d3, so a later wheel or pan continues from here and a
    // stored view is saved as for any other zoom.
    function zoomBy(dir) {
      if (typeof dir !== 'number' || !Number.isFinite(dir)) {
        throw new Error('pjx.graph.zoomBy: dir must be a finite number');
      }
      view.zoom.scaleBy(d3.select(canvas), ZOOM_STEP ** dir,
        [canvas.clientWidth / 2, canvas.clientHeight / 2]);
    }

    // A node's class goes on the node findNode picks; an edge's on each of
    // its visible paths, never on the hit path.
    function selectedElements() {
      if (selected === null) return [];
      if (selected.kind === 'node') {
        const node = findNode(selected.id);
        return node ? [node] : [];
      }
      return drawn.filter((el) => el.classList.contains('pjx-graph__edge')
        && el.getAttribute('data-edge-id') === selected.id);
    }

    function mark(on) {
      if (selected === null) return;
      const name = 'pjx-graph__' + selected.kind + '--selected';
      selectedElements().forEach((el) => el.classList.toggle(name, on));
    }

    // The before- event can veto the change; the plain one reports it once
    // the DOM shows it. Choosing the current selection again changes nothing.
    function choose(kind, id) {
      if (selected !== null && selected.kind === kind && selected.id === id) return true;
      const suffix = kind === 'edge' ? '-edge' : '';
      const allowed = root.dispatchEvent(new CustomEvent('pjx:graph:before-select' + suffix,
        { bubbles: true, cancelable: true, detail: { id: id } }));
      if (!allowed) return false;
      mark(false);
      selected = { kind: kind, id: id };
      mark(true);
      root.dispatchEvent(new CustomEvent('pjx:graph:select' + suffix,
        { bubbles: true, detail: { id: id } }));
      return true;
    }

    function select(id) {
      if (typeof id !== 'string') throw new Error('pjx.graph.select: expected a string id');
      if (!findNode(id)) throw new Error('pjx.graph.select: no node "' + id + '"');
      return choose('node', id);
    }

    function deselect() {
      if (selected === null) return;
      mark(false);
      selected = null;
      root.dispatchEvent(new CustomEvent('pjx:graph:deselect', { bubbles: true, detail: null }));
    }

    // An unknown or display:none node has no box to join.
    function shown(id) {
      const node = findNode(id);
      return node !== null && node.getClientRects().length > 0;
    }

    function drawAll() {
      drawn.forEach((el) => el.remove());
      drawn = [];
      // A span with no edge id at all is not an edge; an empty one still is.
      const edges = edgesOf(root, viewport)
        .filter((edge) => edge.hasAttribute('data-edge-id'))
        .filter((edge) => shown(edge.getAttribute('data-from')) && shown(edge.getAttribute('data-to')));
      // Counted over the edges actually drawn, so a lone survivor is unfanned.
      const totals = new Map();
      edges.forEach((edge) => totals.set(pairOf(edge), (totals.get(pairOf(edge)) || 0) + 1));
      const seen = new Map();
      edges.forEach((edge, index) => {
        const pair = pairOf(edge);
        const nth = seen.get(pair) || 0;
        seen.set(pair, nth + 1);
        const from = edge.getAttribute('data-from');
        const to = edge.getAttribute('data-to');
        const id = attr(edge, 'data-edge-id');
        const d = edgePath(outAnchor(from, attr(edge, 'data-port')), inAnchor(to),
          fanOffset(nth, totals.get(pair)));
        const state = attr(edge, 'data-state');
        // A state is the app's word; only a single token can become a class.
        const modifier = /^\S+$/.test(state) ? ' pjx-graph__edge--' + state : '';
        // The wide transparent twin goes first, underneath, as the press target.
        drawn.push(svg('path', { class: 'pjx-graph__edge-hit', d: d, 'data-edge-id': id }));
        drawn.push(svg('path', {
          class: 'pjx-graph__edge' + modifier,
          id: prefix + index,
          d: d,
          'data-edge-id': id,
          'data-from': from,
          'data-to': to,
          'data-state': state,
        }));
        const label = attr(edge, 'data-label');
        if (label) {
          const text = svg('text', { class: 'pjx-graph__edge-label', 'data-edge-id': id });
          const along = svg('textPath', {
            href: '#' + prefix + index, startOffset: '50%', 'text-anchor': 'middle',
          });
          // Text, never markup: a label shows exactly as written.
          along.textContent = label;
          text.append(along);
          drawn.push(text);
        }
      });
      plane.append(...drawn);
      // The redrawn paths are new elements, so the selection's class goes
      // back on; a selected edge that is gone keeps its selection for later.
      mark(true);
    }

    // Cleared even if drawing throws, so a stale index never outlives it.
    function redraw() {
      index = indexNodes();
      try {
        drawAll();
      } finally {
        index = null;
      }
    }

    function drawEdges() {
      redraw();
      root.dispatchEvent(new CustomEvent('pjx:graph:rendered', { bubbles: true, detail: null }));
    }

    // While a node or a wire is held, a reconcile only marks the stage
    // dirty, so nothing moves under the pointer; the last gesture to end
    // runs the one reconcile that was put off.
    let gestures = 0;
    let dirty = false;

    function reconcile() {
      // A dropped stage is detached for good, so nothing it would draw is seen.
      if (signal.aborted) return;
      if (gestures > 0) {
        dirty = true;
        return;
      }
      placeChanged();
      drawEdges();
    }

    function beginGesture() {
      gestures += 1;
    }

    // Called after the gesture's own work, so a drop is stored before the
    // flush places the nodes. Cleared first, so a throw inside the flush
    // cannot leave the stage stuck dirty.
    function endGesture() {
      gestures -= 1;
      if (gestures > 0 || !dirty) return;
      dirty = false;
      reconcile();
    }

    // Only this stage's nodes with a server position drag: a drop needs a
    // base to anchor it, and a port or form control keeps its own press.
    function draggable(target) {
      if (target.closest('[data-pjx-graph]') !== root) return null;
      const node = target.closest('[data-node-id]');
      if (!node || !viewport.contains(node)) return null;
      const used = target.closest('[data-pjx-graph-port], ' + INTERACTIVE);
      if (used && node.contains(used)) return null;
      if (coordinate(node, 'x') === null || coordinate(node, 'y') === null) return null;
      return node;
    }

    // The click that follows a dragged release must not select; armed for
    // that one click only, since a release does not always produce one.
    let swallow = false;

    function swallowClick() {
      swallow = true;
      setTimeout(() => { swallow = false; }, 0);
    }

    function listenForDrag() {
      let press = null;

      function follow(event) {
        if (event.pointerId !== press.pointerId) return;
        const dx = event.clientX - press.clientX;
        const dy = event.clientY - press.clientY;
        if (!press.dragging && Math.hypot(dx, dy) <= DRAG_SLOP) return;
        press.dragging = true;
        const k = d3.zoomTransform(canvas).k;
        // Whole pixels, so the live position is the one the drop reports.
        press.x = Math.round(press.startX + dx / k);
        press.y = Math.round(press.startY + dy / k);
        moveTo(press.node, press.x, press.y);
        // Silent: rendered follows a reconcile, not every pointer move.
        redraw();
      }

      function end(event) {
        if (event.pointerId !== press.pointerId) return;
        const done = press;
        press = null;
        window.removeEventListener('pointermove', follow);
        window.removeEventListener('pointerup', end);
        window.removeEventListener('pointercancel', end);
        document.removeEventListener('selectstart', block);
        if (done.dragging) drop(done);
        endGesture();
      }

      // Read from the pressed element, even if the app has since replaced
      // it, so the drop keeps the base the user dragged from.
      function drop(done) {
        swallowClick();
        const id = done.node.getAttribute('data-node-id');
        const baseX = coordinate(done.node, 'x');
        const baseY = coordinate(done.node, 'y');
        if (view.key && baseX !== null && baseY !== null) {
          saveOverride(view.key, id, { x: done.x, y: done.y, base: { x: baseX, y: baseY } });
        }
        root.dispatchEvent(new CustomEvent('pjx:graph:move',
          { bubbles: true, detail: { id: id, x: done.x, y: done.y } }));
      }

      function block(event) {
        event.preventDefault();
      }

      canvas.addEventListener('pointerdown', (event) => {
        if (press !== null || event.button !== 0 || event.ctrlKey) return;
        const node = draggable(event.target);
        if (!node) return;
        // Where the node shows now: its drop, or the server's position.
        const style = node.style;
        press = {
          node: node, pointerId: event.pointerId, dragging: false,
          clientX: event.clientX, clientY: event.clientY,
          startX: parseFloat(style.getPropertyValue('--pjx-graph-node-x')),
          startY: parseFloat(style.getPropertyValue('--pjx-graph-node-y')),
        };
        // On window, so the drag goes on outside the canvas. Tied to the
        // stage's life, so dropping the stage abandons the drag.
        window.addEventListener('pointermove', follow, { signal: signal });
        window.addEventListener('pointerup', end, { signal: signal });
        window.addEventListener('pointercancel', end, { signal: signal });
        document.addEventListener('selectstart', block, { signal: signal });
        // From the press, not from the slop: a reconcile before the drag
        // starts would place the node the user is about to move.
        beginGesture();
      });
    }

    // The nearest node, when it is one of this stage's own.
    function ownNode(target) {
      const node = target.closest('[data-node-id]');
      return node && viewport.contains(node) && node.closest('[data-pjx-graph]') === root
        ? node : null;
    }

    // Starts on an out-port and ends on another node; the app creates the
    // edge, so the engine only reports the request.
    function listenForWire() {
      let wire = null;

      function clearGhost() {
        if (wire.ghost) wire.ghost.remove();
        wire.ghost = null;
      }

      function follow(event) {
        if (event.pointerId !== wire.pointerId) return;
        const dx = event.clientX - wire.clientX;
        const dy = event.clientY - wire.clientY;
        if (!wire.dragging && Math.hypot(dx, dy) <= DRAG_SLOP) return;
        wire.dragging = true;
        const start = outAnchor(wire.from, wire.port);
        // A source swapped out mid-gesture has nowhere to start from.
        if (!start) {
          clearGhost();
          return;
        }
        if (!wire.ghost) {
          // Outside drawn, so a redraw during the gesture keeps it.
          wire.ghost = svg('path', { class: 'pjx-graph__wire' });
          plane.append(wire.ghost);
        }
        wire.ghost.setAttribute('d', edgePath(start, toWorld(event.clientX, event.clientY), 0));
      }

      function end(event) {
        if (event.pointerId !== wire.pointerId) return;
        clearGhost();
        const done = wire;
        wire = null;
        window.removeEventListener('pointermove', follow);
        window.removeEventListener('pointerup', end);
        window.removeEventListener('pointercancel', end);
        document.removeEventListener('selectstart', block);
        if (done.dragging) connect(done, event);
        endGesture();
      }

      // Before the flush, so the drop is hit-tested against the nodes the
      // user saw while wiring.
      function connect(done, event) {
        swallowClick();
        if (event.type !== 'pointerup' || !findNode(done.from)) return;
        // The ghost takes no pointer events, so it never hides the node below.
        const hit = document.elementFromPoint(event.clientX, event.clientY);
        const target = hit && ownNode(hit);
        if (!target) return;
        const to = target.getAttribute('data-node-id');
        // Never a self-loop: a drop back on the source cancels.
        if (to === done.from) return;
        root.dispatchEvent(new CustomEvent('pjx:graph:wire',
          { bubbles: true, detail: { from: done.from, port: done.port, to: to } }));
      }

      function block(event) {
        event.preventDefault();
      }

      canvas.addEventListener('pointerdown', (event) => {
        if (wire !== null || event.button !== 0 || event.ctrlKey) return;
        const port = event.target.closest('[data-pjx-graph-port="out"]');
        const node = port && ownNode(port);
        if (!node) return;
        wire = {
          from: node.getAttribute('data-node-id'), port: attr(port, 'data-port'),
          pointerId: event.pointerId, dragging: false, ghost: null,
          clientX: event.clientX, clientY: event.clientY,
        };
        // On window, so a release outside the canvas still ends the wire.
        // Tied to the stage's life, so dropping the stage abandons the wire.
        window.addEventListener('pointermove', follow, { signal: signal });
        window.addEventListener('pointerup', end, { signal: signal });
        window.addEventListener('pointercancel', end, { signal: signal });
        document.addEventListener('selectstart', block, { signal: signal });
        beginGesture();
      });
    }

    // Capturing, so it runs before the selection listener on the canvas.
    canvas.addEventListener('click', (event) => {
      if (!swallow) return;
      swallow = false;
      event.stopImmediatePropagation();
    }, true);

    listenForSelection(root, canvas, viewport, plane, choose, deselect);
    listenForDrag();
    listenForWire();
    return {
      root: root, box: box, inAnchor: inAnchor, outAnchor: outAnchor, fit: fit, zoomBy: zoomBy,
      drawEdges: drawEdges, select: select, deselect: deselect, reconcile: reconcile,
    };
  }

  // An edge or a node is drawn from these. style stays unwatched, since
  // placing a node writes it.
  const WATCHED = ['data-x', 'data-y', 'data-from', 'data-to', 'data-port', 'data-state',
    'data-label'];

  // The edge planes hold drawing only, the engine's own and a nested stage's,
  // so their changes are skipped; otherwise every redraw would schedule the
  // next. A watched name on the app's own markup inside a node is not ours.
  function concernsGraph(m) {
    if (m.target.closest('svg.pjx-graph__edge-plane')) return false;
    return m.type === 'childList' || m.target.matches('[data-pjx-graph-edge], [data-node-id]');
  }

  // Swaps inside the viewport, and edits to what an edge or node is drawn
  // from, reconcile once, in the next frame, however many records they make.
  function observeViewport(viewport, instance, signal) {
    let pending = false;
    const observer = new MutationObserver((mutations) => {
      if (pending || !mutations.some(concernsGraph)) return;
      pending = true;
      requestAnimationFrame(() => {
        pending = false;
        instance.reconcile();
      });
    });
    observer.observe(viewport, { childList: true, subtree: true, attributeFilter: WATCHED });
    signal.addEventListener('abort', () => observer.disconnect());
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
    const plane = part(viewport, 'svg.pjx-graph__edge-plane', true);
    part(viewport, '.pjx-graph__nodes', false);
    const life = new AbortController();
    const view = attachZoom(root, canvas, viewport);
    const instance = createInstance(root, canvas, viewport, plane, view, life.signal);
    instances.set(root, instance);
    lives.set(root, life);
    observeViewport(viewport, instance, life.signal);
    listenForControls(root, canvas, instance);
    // A restored view is where the user left off; only a fresh stage is framed.
    // Edges are drawn before ready, so whatever waits on ready sees them.
    if (view.restored) {
      instance.drawEdges();
      settle(root, canvas, view);
    } else {
      whenLaidOut(canvas, life.signal, () => {
        instance.fit();
        instance.drawEdges();
        settle(root, canvas, view);
      });
    }
    return instance;
  }

  function get(root) {
    return instances.get(root) || null;
  }

  // A root that has left the document is gone for good, so its instance
  // stops and get() forgets it; a root put back later is mounted afresh.
  function drop(root) {
    const life = lives.get(root);
    if (!life) return;
    life.abort();
    lives.delete(root);
    instances.delete(root);
  }

  // The stages in a subtree, its own root included.
  function stagesIn(subtree) {
    const stages = Array.from(subtree.querySelectorAll('[data-pjx-graph]'));
    if (subtree.matches && subtree.matches('[data-pjx-graph]')) {
      stages.unshift(subtree);
    }
    return stages;
  }

  function boot(subtree) {
    stagesIn(subtree).forEach((stage) => {
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
    // is seen before its children exist and would fail to mount. A batch is
    // judged by where its nodes ended up: a root moved within it is still in
    // the document and keeps its instance, and one added and removed within
    // it is not mounted, since nothing would be left to drop it.
    new MutationObserver((mutations) => {
      mutations.forEach((m) => {
        m.removedNodes.forEach((node) => {
          if (node.nodeType === 1 && !node.isConnected) stagesIn(node).forEach(drop);
        });
        m.addedNodes.forEach((node) => {
          if (node.nodeType === 1 && node.isConnected) boot(node);
        });
      });
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
