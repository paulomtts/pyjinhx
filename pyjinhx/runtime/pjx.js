(function () {
  function pjxManifest() {
    return Array.prototype.map.call(
      document.querySelectorAll("[data-pjx-id]"),
      function (el) {
        return {
          id: el.dataset.pjxId,
          type: el.dataset.pjxType,
          hash: el.dataset.pjxHash,
          key: el.dataset.pjxKey ?? null,
        };
      }
    );
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
  });
})();
