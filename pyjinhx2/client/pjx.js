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

  document.body.addEventListener("htmx:configRequest", function () {});

  pjx.manifest = pjxManifest;
  pjx.loadedAssets = pjxLoadedAssets;
  pjx.trigger = pjxTrigger;
  window.pjx = pjx;
})();
