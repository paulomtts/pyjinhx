// pjx.js: scans the DOM for mounted [data-pjx-id] regions and stamps
// X-PJX-Mounted/X-PJX-Assets/X-PJX-Trigger request headers on every htmx
// request, and applies the one swap mechanic htmx core can't do natively --
// relocating [data-pjx-asset] head assets that arrive via OOB or cold render.
// Loading state is dispatch-only: core tracks region/page loading state and
// fires pjx:region-loading-*/pjx:page-loading-* events, never touching
// classList itself -- that's the loading-indicator/page-loader artifacts' job.
(function () {
  var pjx = {};

  function pjxManifest() {
    return Array.prototype.map.call(
      document.querySelectorAll("[data-pjx-id]"),
      function (el) {
        var entry = {
          id: el.dataset.pjxId,
          type: el.dataset.pjxType,
          hash: el.dataset.pjxHash,
        };
        if (el.dataset.pjxLoad) {
          entry.load = el.dataset.pjxLoad;
        }
        return entry;
      }
    );
  }

  function pjxLoadedAssets() {
    var tokens = [];
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-pjx-asset]"),
      function (el) {
        var token = el.getAttribute("data-pjx-asset");
        if (token && tokens.indexOf(token) === -1) {
          tokens.push(token);
        }
      }
    );
    return tokens;
  }

  function pjxRoot(el) {
    return el && el.closest ? el.closest("[data-pjx-id]") : null;
  }

  function pjxTrigger(elt) {
    var root = pjxRoot(elt);
    return root ? { id: root.dataset.pjxId } : null;
  }

  function pjxConfigRequest(evt) {
    var headers = evt.detail && evt.detail.headers;
    if (!headers) {
      return;
    }
    headers["X-PJX-Mounted"] = JSON.stringify(pjxManifest());
    headers["X-PJX-Assets"] = JSON.stringify(pjxLoadedAssets());
    var trigger = pjxTrigger(evt.detail.elt);
    if (trigger) {
      headers["X-PJX-Trigger"] = JSON.stringify(trigger);
    }
  }

  // A builtin style and the app style restyling it tie at specificity (both
  // are single classes on the same element), so whichever lands later in
  // <head> wins the tie -- appendChild alone can't guarantee a bare app
  // selector wins if its builtin counterpart happens to arrive after it.
  // Builtin styles carry data-pjx-origin="builtin" (server-emitted, #1058);
  // inserting one before the first app style already resident keeps builtins
  // ahead of app CSS no matter which one this page saw first.
  function pjxInsertHeadStyle(node) {
    if (node.getAttribute("data-pjx-origin") === "builtin") {
      var appStyle = document.head.querySelector(
        'style[data-pjx-asset]:not([data-pjx-origin="builtin"])'
      );
      if (appStyle) {
        document.head.insertBefore(node, appStyle);
        return;
      }
    }
    document.head.appendChild(node);
  }

  // htmx core silently drops hx-swap-oob swaps that target <head>, so the
  // component assets the server carries alongside OOB fragments have to be
  // parsed out of the raw response and appended here. Fresh nodes: a parsed
  // <script> clone never executes. Dedup is per token, not per node, because
  // swaps replace the nodes that carried the previous copy.
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
          return;
        }
        var fresh = document.createElement(tag);
        fresh.setAttribute("data-pjx-asset", token);
        var origin = node.getAttribute("data-pjx-origin");
        if (origin) {
          fresh.setAttribute("data-pjx-origin", origin);
        }
        if (tag === "script" && node.src) {
          fresh.src = node.src;
        } else {
          fresh.textContent = node.textContent;
        }
        if (tag === "style") {
          pjxInsertHeadStyle(fresh);
        } else {
          document.head.appendChild(fresh);
        }
      }
    );
  }

  function pjxApplyHeadAssetsFromRequest(evt) {
    var xhr = evt.detail && evt.detail.xhr;
    pjxApplyHeadAssets(xhr && xhr.responseText);
  }

  // A cold render emits <style data-pjx-asset> inline in the body. If that style
  // sits inside a region that later re-renders, the swap deletes it and the
  // server -- seeing its token in X-PJX-Assets -- won't resend it, leaving the
  // content unstyled. <head> is the durable home. Styles only: a <script>'s
  // effect outlives its node, and re-appending it would re-execute it.
  function pjxPromoteInlineAssets() {
    Array.prototype.forEach.call(
      document.body.querySelectorAll("style[data-pjx-asset]"),
      function (node) {
        var token = node.getAttribute("data-pjx-asset");
        if (document.head.querySelector('[data-pjx-asset="' + token + '"]')) {
          node.remove();
          return;
        }
        pjxInsertHeadStyle(node); // relocates body -> head, builtins first
      }
    );
  }

  var pjxLoadingByXhr = new Map(); // xhr -> [region id, ...]
  var pjxLoading = {}; // region id -> in-flight request count (ref-count)

  function pjxReacts(el) {
    var value = el.getAttribute("data-pjx-reacts");
    return value ? value.split(" ").filter(Boolean) : [];
  }

  function pjxLoadingClass(el) {
    return "pjx-loading--" + (el.getAttribute("data-pjx-loading") || "skeleton");
  }

  function pjxRegion(id) {
    var key = window.CSS && CSS.escape ? CSS.escape(id) : id;
    return document.querySelector('[data-pjx-id="' + key + '"]');
  }

  // the [data-pjx-loading] elements belonging to a region (itself and/or inner
  // elements, but not those owned by a nested reactive region)
  function pjxLoadingTargets(region) {
    var targets = [];
    if (region.getAttribute("data-pjx-loading")) {
      targets.push(region);
    }
    Array.prototype.forEach.call(
      region.querySelectorAll("[data-pjx-loading]"),
      function (el) {
        if (el.closest("[data-pjx-id][data-pjx-reacts]") === region) {
          targets.push(el);
        }
      }
    );
    return targets;
  }

  // Dispatch-only, like pjxToast: applying the class is the loading-indicator
  // artifact's job, so core stays a pure state machine over region ids.
  function pjxFire(name, detail) {
    document.dispatchEvent(
      new CustomEvent(name, { detail: detail || {}, bubbles: false })
    );
  }

  function pjxLight(region, ids) {
    var id = region.getAttribute("data-pjx-id");
    if (!id || ids.indexOf(id) !== -1) {
      return;
    }
    var targets = pjxLoadingTargets(region);
    if (!targets.length) {
      return;
    }
    pjxLoading[id] = (pjxLoading[id] || 0) + 1;
    ids.push(id);
    pjxFire("pjx:region-loading-start", { id: id });
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
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-pjx-id][data-pjx-reacts]"),
      function (region) {
        var reacts = pjxReacts(region).some(function (key) {
          return dirty[key];
        });
        if (!reacts) {
          return;
        }
        // keyed regions: light only the instance matching the trigger's load key
        var regionLoad = region.getAttribute("data-pjx-load");
        if (regionLoad === null || regionLoad === triggerLoad) {
          pjxLight(region, ids);
        }
      }
    );
    // a trigger may name extra regions to light (e.g. rows a bulk action removes)
    var extra = root.getAttribute("data-pjx-loading-extra");
    if (extra) {
      Array.prototype.forEach.call(
        document.querySelectorAll(extra),
        function (region) {
          pjxLight(region, ids);
        }
      );
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
      return; // already released (loadend and the htmx event both fire)
    }
    pjxLoadingByXhr.delete(xhr);
    ids.forEach(function (id) {
      pjxRelease(id);
    });
  }

  // one ref released; at zero the region goes dark. Clamped so a duplicate
  // release can never drive the count negative and strand a region "lit".
  function pjxRelease(id) {
    pjxLoading[id] = (pjxLoading[id] || 0) - 1;
    if (pjxLoading[id] > 0) {
      return;
    }
    delete pjxLoading[id];
    pjxFire("pjx:region-loading-end", { id: id });
  }

  // a swap can replace a region another in-flight request still needs lit
  function pjxReapplyLoading() {
    Object.keys(pjxLoading).forEach(function (id) {
      pjxFire("pjx:region-loading-start", { id: id });
    });
  }

  // The dispatch half of the toast API. Rendering belongs to an L4 toast-host
  // builtin listening for this event, so core stays DOM-template-free.
  // Dispatched with bubbles: true so it reaches the window-level listener
  // the toast host builtin registers, matching the HX-Trigger toast path
  // which already fires on the triggering element and bubbles to window.
  function pjxToast(payload) {
    document.dispatchEvent(
      new CustomEvent("pjx:toast", { detail: payload || {}, bubbles: true })
    );
  }

  var pjxPageLoading = 0;

  // Toggle the page-level loading state. Only the state and the event are
  // core's; the overlay class and its CSS belong to the page-loader artifact.
  function pjxLoaderPage(on) {
    if (on) {
      pjxPageLoading += 1;
      pjxFire("pjx:page-loading-start", {});
      return;
    }
    var was = pjxPageLoading;
    pjxPageLoading = Math.max(0, pjxPageLoading - 1);
    if (was > 0 && pjxPageLoading === 0) {
      pjxFire("pjx:page-loading-end", {});
    }
  }

  // Same ref-count the htmx wiring uses, so a manual show and an in-flight
  // request over the same region can't switch each other off.
  function pjxLoaderRegion(id, on) {
    var region = pjxRegion(id);
    if (!region) {
      return;
    }
    if (on) {
      pjxLight(region, []);
      return;
    }
    if (pjxLoading[id]) {
      pjxRelease(id);
    }
  }

  pjx.manifest = pjxManifest;
  pjx.loadedAssets = pjxLoadedAssets;
  pjx.trigger = pjxTrigger;
  pjx.applyHeadAssets = pjxApplyHeadAssets;
  pjx.promoteInlineAssets = pjxPromoteInlineAssets;
  pjx.toast = pjxToast;
  pjx.loader = { page: pjxLoaderPage, region: pjxLoaderRegion };
  pjx.loadingCount = function (id) {
    return pjxLoading[id] || 0;
  };
  pjx.region = pjxRegion;
  pjx.loadingTargets = pjxLoadingTargets;
  pjx.loadingClass = pjxLoadingClass;
  // Merge, never replace: builtins (popover, toast host) install themselves on
  // this same namespace and self-guard, so a second execution of the bundle
  // must not throw away keys the first execution's builtins left behind.
  window.pjx = Object.assign(window.pjx || {}, pjx);

  if (!window.htmx) {
    console.error(
      "[pyjinhx] htmx not found — reactivity (OOB swaps) will not work. " +
        "Load htmx before pjx.js."
    );
  }

  pjxPromoteInlineAssets();
  document.body.addEventListener("htmx:configRequest", pjxConfigRequest);
  document.body.addEventListener("htmx:afterRequest", pjxApplyHeadAssetsFromRequest);
  document.body.addEventListener("htmx:beforeRequest", pjxBeginLoading);
  document.body.addEventListener("htmx:afterOnLoad", pjxEndLoading);
  document.body.addEventListener("htmx:responseError", pjxEndLoading);
  document.body.addEventListener("htmx:timeout", pjxEndLoading);
  document.body.addEventListener("htmx:sendError", pjxEndLoading);
  document.body.addEventListener("htmx:abort", pjxEndLoading);
  document.body.addEventListener("htmx:afterSettle", pjxReapplyLoading);
})();
