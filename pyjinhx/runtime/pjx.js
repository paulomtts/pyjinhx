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
    var urls = [];
    Array.prototype.forEach.call(
      document.querySelectorAll('script[src], link[rel="stylesheet"][href]'),
      function (el) {
        var url = el.src || el.href;
        if (url) {
          urls.push(url);
        }
      }
    );
    return urls;
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
    style.textContent =
      ".pjx-loading{position:relative;overflow:hidden}" +
      ".pjx-loading>*{opacity:.55;transition:opacity .15s ease}" +
      ".pjx-loading::after{content:'';position:absolute;inset:0;pointer-events:none;" +
      "background:linear-gradient(90deg,transparent,rgba(127,127,127,.18) 50%,transparent);" +
      "background-size:200% 100%;animation:pjx-shimmer 1.2s ease-in-out infinite}" +
      "@keyframes pjx-shimmer{from{background-position:100% 0}to{background-position:-100% 0}}";
    document.head.appendChild(style);
  }

  var pjxLoadingByXhr = new Map();

  function pjxReacts(el) {
    var value = el.getAttribute("data-pjx-reacts");
    return value ? value.split(" ").filter(Boolean) : [];
  }

  function pjxBeginLoading(evt) {
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
    var marked = [];
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-pjx-skeleton][data-pjx-reacts]"),
      function (el) {
        var hit = pjxReacts(el).some(function (key) {
          return dirty[key];
        });
        if (hit) {
          el.classList.add("pjx-loading");
          marked.push(el);
        }
      }
    );
    if (marked.length) {
      pjxLoadingByXhr.set(xhr, marked);
    }
  }

  function pjxEndLoading(evt) {
    var xhr = evt.detail && evt.detail.xhr;
    var marked = xhr && pjxLoadingByXhr.get(xhr);
    if (!marked) {
      return;
    }
    marked.forEach(function (el) {
      el.classList.remove("pjx-loading");
    });
    pjxLoadingByXhr.delete(xhr);
  }

  pjxInjectStyle();
  document.body.addEventListener("htmx:beforeRequest", pjxBeginLoading);
  document.body.addEventListener("htmx:afterOnLoad", pjxEndLoading);
  document.body.addEventListener("htmx:responseError", pjxEndLoading);
  document.body.addEventListener("htmx:timeout", pjxEndLoading);
  document.body.addEventListener("htmx:sendError", pjxEndLoading);
  document.body.addEventListener("htmx:abort", pjxEndLoading);
})();
