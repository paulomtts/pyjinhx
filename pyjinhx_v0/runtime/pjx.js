(function () {
  function pjxRoot(el) {
    return el && el.closest ? el.closest("[data-pjx-id]") : null;
  }

  function pjxManifest() {
    return Array.prototype.map.call(
      document.querySelectorAll("[data-pjx-id]"),
      function (el) {
        var entry = {
          id: el.dataset.pjxId,
          type: el.dataset.pjxType,
          hash: el.dataset.pjxHash,
        };
        if (el.dataset.pjxLoad != null && el.dataset.pjxLoad !== "") {
          entry.load = el.dataset.pjxLoad;
        }
        return entry;
      }
    );
  }

  function pjxTrigger(elt) {
    var root = pjxRoot(elt);
    if (!root) {
      return null;
    }
    return { id: root.dataset.pjxId };
  }

  function pjxLoadedAssets() {
    var tokens = [];
    Array.prototype.forEach.call(
      document.querySelectorAll('[data-pjx-asset]'),
      function (el) { tokens.push(el.getAttribute('data-pjx-asset')); }
    );
    return tokens;
  }

  document.body.addEventListener("htmx:configRequest", function (evt) {
    evt.detail.headers["X-PJX-Mounted"] = JSON.stringify(pjxManifest());
    evt.detail.headers["X-PJX-Assets"] = JSON.stringify(pjxLoadedAssets());
    var trigger = pjxTrigger(evt.detail.elt);
    if (trigger) {
      evt.detail.headers["X-PJX-Trigger"] = JSON.stringify(trigger);
    }
  });

  function pjxInjectStyle() {
    if (document.getElementById("pjx-style")) {
      return;
    }
    var style = document.createElement("style");
    style.id = "pjx-style";
    // styles read overridable --pjx-* custom properties (set them in your own CSS)
    style.textContent =
      ".pjx-loading--skeleton,.pjx-loading--spinner{pointer-events:none}" +
      ".pjx-loading--skeleton{color:transparent !important;" +
      "border-radius:var(--pjx-skeleton-radius,6px);background-image:linear-gradient(90deg," +
      "var(--pjx-skeleton-color,rgba(127,127,127,.12))," +
      "var(--pjx-skeleton-highlight,rgba(127,127,127,.30)) 50%," +
      "var(--pjx-skeleton-color,rgba(127,127,127,.12)));background-size:200% 100%;" +
      "animation:pjx-shimmer var(--pjx-skeleton-speed,1.2s) ease-in-out infinite}" +
      ".pjx-loading--skeleton *{visibility:hidden}" +
      ".pjx-loading--spinner{position:relative}" +
      ".pjx-loading--spinner::before{content:'';position:absolute;inset:0;" +
      "background:var(--pjx-spinner-overlay,rgba(0,0,0,.45));" +
      "backdrop-filter:blur(var(--pjx-spinner-blur,2px));" +
      "-webkit-backdrop-filter:blur(var(--pjx-spinner-blur,2px));border-radius:inherit}" +
      ".pjx-loading--spinner::after{content:'';position:absolute;top:50%;left:50%;" +
      "width:var(--pjx-spinner-size,1.1em);height:var(--pjx-spinner-size,1.1em);" +
      "margin:calc(var(--pjx-spinner-size,1.1em)/-2) 0 0 calc(var(--pjx-spinner-size,1.1em)/-2);" +
      "box-sizing:border-box;border:var(--pjx-spinner-thickness,2px) solid " +
      "var(--pjx-spinner-track,rgba(255,255,255,.4));" +
      "border-top-color:var(--pjx-spinner-color,rgba(255,255,255,.95));" +
      "border-radius:50%;animation:pjx-spin var(--pjx-spinner-speed,.6s) linear infinite}" +
      "@keyframes pjx-shimmer{from{background-position:100% 0}to{background-position:-100% 0}}" +
      "@keyframes pjx-spin{to{transform:rotate(360deg)}}";
    document.head.appendChild(style);
  }

  var pjxLoadingByXhr = new Map();  // xhr -> [region id, ...]
  var pjxLoading = {};              // region id -> in-flight request count (ref-count)

  function pjxReacts(el) {
    var value = el.getAttribute("data-pjx-reacts");
    return value ? value.split(" ").filter(Boolean) : [];
  }

  function pjxLoadingClass(el) {
    return "pjx-loading--" + (el.getAttribute("data-pjx-loading") || "skeleton");
  }

  function pjxRegion(id) {
    return document.querySelector('[data-pjx-id="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]');
  }

  // the [data-pjx-loading] elements belonging to a region (itself and/or inner
  // elements, but not those owned by a nested reactive region)
  function pjxLoadingTargets(region) {
    var targets = [];
    if (region.getAttribute("data-pjx-loading")) {
      targets.push(region);
    }
    Array.prototype.forEach.call(region.querySelectorAll("[data-pjx-loading]"), function (el) {
      if (el.closest("[data-pjx-id][data-pjx-reacts]") === region) {
        targets.push(el);
      }
    });
    return targets;
  }

  function pjxBeginLoading(evt) {
    if (evt.defaultPrevented) {
      return; // cancelled request: its xhr is never sent, so loadend never fires
    }
    var xhr = evt.detail && evt.detail.xhr;
    var elt = evt.detail && evt.detail.elt;
    var root = elt && elt.closest ? elt.closest("[data-pjx-id][data-pjx-reacts]") : null;
    if (!xhr || !root) {
      return;
    }
    var dirty = {};
    pjxReacts(root).forEach(function (key) {
      dirty[key] = true;
    });
    var triggerLoad = root.getAttribute("data-pjx-load");
    var ids = [];
    function light(region) {
      var id = region.getAttribute("data-pjx-id");
      if (!id || ids.indexOf(id) !== -1) {
        return;
      }
      var targets = pjxLoadingTargets(region);
      if (!targets.length) {
        return;
      }
      targets.forEach(function (t) { t.classList.add(pjxLoadingClass(t)); });
      pjxLoading[id] = (pjxLoading[id] || 0) + 1;
      ids.push(id);
    }
    // light every reactive region reacting to the predicted keys; the template
    // decides which element(s) inside each region carry data-pjx-loading
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-pjx-id][data-pjx-reacts]"),
      function (region) {
        if (!pjxReacts(region).some(function (key) { return dirty[key]; })) {
          return;
        }
        // keyed regions: flag only the instance matching the trigger's load key
        var regionLoad = region.getAttribute("data-pjx-load");
        if (regionLoad === null || regionLoad === triggerLoad) {
          light(region);
        }
      }
    );
    // a trigger may name extra regions to flag (e.g. rows a bulk action removes)
    var extra = root.getAttribute("data-pjx-loading-extra");
    if (extra) {
      Array.prototype.forEach.call(document.querySelectorAll(extra), light);
    }
    if (ids.length) {
      pjxLoadingByXhr.set(xhr, ids);
      // loadend always fires (load/error/abort), even when htmx discards the
      // response of a superseded request -- a reliable cue to release the refs
      xhr.addEventListener("loadend", function () {
        pjxEndLoading(xhr);
      });
    }
  }

  function pjxEndLoading(xhrOrEvt) {
    var xhr = xhrOrEvt && xhrOrEvt.detail ? xhrOrEvt.detail.xhr : xhrOrEvt;
    var ids = xhr && pjxLoadingByXhr.get(xhr);
    if (!ids) {
      return;
    }
    pjxLoadingByXhr.delete(xhr);
    ids.forEach(function (id) {
      pjxLoading[id] -= 1;
      if (pjxLoading[id] <= 0) {
        delete pjxLoading[id];
        var region = pjxRegion(id);
        if (region) {
          pjxLoadingTargets(region).forEach(function (t) {
            t.classList.remove(pjxLoadingClass(t));
          });
        }
      }
    });
  }

  // a swap can replace a region another in-flight request still needs lit
  function pjxReapplyLoading() {
    Object.keys(pjxLoading).forEach(function (id) {
      var region = pjxRegion(id);
      if (region) {
        pjxLoadingTargets(region).forEach(function (t) {
          t.classList.add(pjxLoadingClass(t));
        });
      }
    });
  }

  // Insert swap-delivered head assets ourselves.  The server carries missing
  // INLINE component assets alongside OOB fragments as
  // <style|script data-pjx-asset hx-swap-oob="beforeend:head">, but htmx core
  // silently drops hx-swap-oob swaps that target <head>, so we parse them out
  // of the response and append them to <head> directly.  A fresh <script>
  // executes on append and a <style> applies on insert.  The server already
  // dedups against the page's loaded tokens (X-PJX-Assets); the per-token <head>
  // check guards against the same asset arriving on two swaps before settle.
  function pjxApplyHeadAssets(html) {
    if (!html || html.indexOf('hx-swap-oob="beforeend:head"') === -1) {
      return;
    }
    var doc = new DOMParser().parseFromString(html, "text/html");
    Array.prototype.forEach.call(
      doc.querySelectorAll("[data-pjx-asset]"),
      function (node) {
        var tag = node.tagName.toLowerCase();
        if (tag !== "style" && tag !== "script") {
          return;
        }
        var token = node.getAttribute("data-pjx-asset");
        if (document.head.querySelector('[data-pjx-asset="' + token + '"]')) {
          return; // already on the page; skip
        }
        var fresh = document.createElement(tag);
        fresh.setAttribute("data-pjx-asset", token);
        if (tag === "script" && node.src) {
          fresh.src = node.src;
        } else {
          fresh.textContent = node.textContent;
        }
        document.head.appendChild(fresh);
      }
    );
  }

  function pjxApplyHeadAssetsFromRequest(evt) {
    var xhr = evt.detail && evt.detail.xhr;
    pjxApplyHeadAssets(xhr && xhr.responseText);
  }

  // On initial load, relocate the document's inline component styles into <head>
  // so they survive region swaps.  Cold (full-page) renders emit
  // <style data-pjx-asset> inline in the body; when that style lives inside a
  // region that later re-renders, the swap deletes it and the server (seeing its
  // token in X-PJX-Assets) won't resend it — leaving the content unstyled (#184).
  // <head> is the durable home, symmetric with pjxApplyHeadAssets for swaps.
  // Styles only: a <script>'s effect persists after node removal, and re-appending
  // it would re-execute it.
  function pjxPromoteInlineAssets() {
    Array.prototype.forEach.call(
      document.body.querySelectorAll('style[data-pjx-asset]'),
      function (node) {
        var token = node.getAttribute('data-pjx-asset');
        if (document.head.querySelector('[data-pjx-asset="' + token + '"]')) {
          node.parentNode.removeChild(node); // duplicate token already durable; drop
          return;
        }
        document.head.appendChild(node); // appendChild relocates body -> head
      }
    );
  }

  if (!window.htmx) {
    console.error(
      "[pyjinhx] htmx not found — reactivity (OOB swaps) will not work. " +
        "Load htmx, or let setup() inject it (inject_htmx defaults to True)."
    );
  }

  pjxInjectStyle();
  pjxPromoteInlineAssets();
  document.body.addEventListener("htmx:beforeRequest", pjxBeginLoading);
  document.body.addEventListener("htmx:afterSettle", pjxReapplyLoading);
  document.body.addEventListener("htmx:afterOnLoad", pjxEndLoading);
  document.body.addEventListener("htmx:responseError", pjxEndLoading);
  document.body.addEventListener("htmx:timeout", pjxEndLoading);
  document.body.addEventListener("htmx:sendError", pjxEndLoading);
  document.body.addEventListener("htmx:abort", pjxEndLoading);
  document.body.addEventListener("htmx:afterRequest", pjxApplyHeadAssetsFromRequest);
})();
