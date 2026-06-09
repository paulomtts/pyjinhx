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
})();
