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
      ".pjx-loading--skeleton,.pjx-loading--spinner{pointer-events:none}" +
      ".pjx-loading--skeleton{color:transparent !important;border-radius:6px;" +
      "background-image:linear-gradient(90deg," +
      "rgba(127,127,127,.12),rgba(127,127,127,.30) 50%,rgba(127,127,127,.12));" +
      "background-size:200% 100%;animation:pjx-shimmer 1.2s ease-in-out infinite}" +
      ".pjx-loading--skeleton *{visibility:hidden}" +
      ".pjx-loading--spinner{position:relative}" +
      ".pjx-loading--spinner::before{content:'';position:absolute;inset:0;" +
      "background:rgba(0,0,0,.45);backdrop-filter:blur(2px);" +
      "-webkit-backdrop-filter:blur(2px);border-radius:inherit}" +
      ".pjx-loading--spinner::after{content:'';position:absolute;top:50%;left:50%;" +
      "width:1.1em;height:1.1em;margin:-.55em 0 0 -.55em;box-sizing:border-box;" +
      "border:2px solid rgba(255,255,255,.4);border-top-color:rgba(255,255,255,.95);" +
      "border-radius:50%;animation:pjx-spin .6s linear infinite}" +
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
    var triggerLoad = root.getAttribute("data-pjx-load");
    var ids = [];
    function mark(el) {
      var id = el.getAttribute("data-pjx-id");
      if (!id) {
        return;
      }
      el.classList.add(pjxLoadingClass(el));
      pjxLoading[id] = (pjxLoading[id] || 0) + 1;
      ids.push(id);
    }
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-pjx-loading][data-pjx-reacts]"),
      function (el) {
        if (!pjxReacts(el).some(function (key) { return dirty[key]; })) {
          return;
        }
        // keyed regions: flag only the instance matching the trigger's load key
        var elLoad = el.getAttribute("data-pjx-load");
        if (elLoad === null || elLoad === triggerLoad) {
          mark(el);
        }
      }
    );
    // a trigger may name extra regions to flag (e.g. rows a bulk action removes)
    var extra = root.getAttribute("data-pjx-loading-extra");
    if (extra) {
      Array.prototype.forEach.call(document.querySelectorAll(extra), mark);
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
        var el = pjxRegion(id);
        if (el) {
          el.classList.remove(pjxLoadingClass(el));
        }
      }
    });
  }

  // a swap can replace a region another in-flight request still needs lit
  function pjxReapplyLoading() {
    Object.keys(pjxLoading).forEach(function (id) {
      var el = pjxRegion(id);
      if (el) {
        el.classList.add(pjxLoadingClass(el));
      }
    });
  }

  pjxInjectStyle();
  document.body.addEventListener("htmx:beforeRequest", pjxBeginLoading);
  document.body.addEventListener("htmx:afterSettle", pjxReapplyLoading);
  document.body.addEventListener("htmx:afterOnLoad", pjxEndLoading);
  document.body.addEventListener("htmx:responseError", pjxEndLoading);
  document.body.addEventListener("htmx:timeout", pjxEndLoading);
  document.body.addEventListener("htmx:sendError", pjxEndLoading);
  document.body.addEventListener("htmx:abort", pjxEndLoading);
})();
