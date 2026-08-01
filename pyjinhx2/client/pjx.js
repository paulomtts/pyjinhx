// pjx.js: scans the DOM for mounted [data-pjx-id] regions and stamps
// X-PJX-Mounted/X-PJX-Assets/X-PJX-Trigger request headers on every htmx
// request, and applies the one swap mechanic htmx core can't do natively --
// relocating [data-pjx-asset] head assets that arrive via OOB or cold render.
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
        document.head.appendChild(node); // appendChild relocates body -> head
      }
    );
  }

  // Injected once so loading indicators work with zero app CSS; every visual
  // knob is a --pjx-* custom property the app can override in its own sheet.
  function pjxInjectStyle() {
    if (document.getElementById("pjx-style")) {
      return;
    }
    var style = document.createElement("style");
    style.id = "pjx-style";
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

  pjx.manifest = pjxManifest;
  pjx.loadedAssets = pjxLoadedAssets;
  pjx.trigger = pjxTrigger;
  pjx.applyHeadAssets = pjxApplyHeadAssets;
  pjx.promoteInlineAssets = pjxPromoteInlineAssets;
  pjx.injectStyle = pjxInjectStyle;
  window.pjx = pjx;

  if (!window.htmx) {
    console.error(
      "[pyjinhx] htmx not found — reactivity (OOB swaps) will not work. " +
        "Load htmx before pjx.js."
    );
  }

  pjxInjectStyle();
  pjxPromoteInlineAssets();
  document.body.addEventListener("htmx:configRequest", pjxConfigRequest);
  document.body.addEventListener("htmx:afterRequest", pjxApplyHeadAssetsFromRequest);
})();
