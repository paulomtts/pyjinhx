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

  pjx.manifest = pjxManifest;
  pjx.loadedAssets = pjxLoadedAssets;
  pjx.trigger = pjxTrigger;
  pjx.applyHeadAssets = pjxApplyHeadAssets;
  window.pjx = pjx;

  document.body.addEventListener("htmx:configRequest", pjxConfigRequest);
  document.body.addEventListener("htmx:afterRequest", pjxApplyHeadAssetsFromRequest);
})();
