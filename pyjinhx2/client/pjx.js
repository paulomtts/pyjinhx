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

  document.body.addEventListener("htmx:configRequest", function () {});

  pjx.manifest = pjxManifest;
  window.pjx = pjx;
})();
