// Applies the page-level loading class off core's page-loading events.
(function () {
  document.addEventListener("pjx:page-loading-start", function () {
    document.documentElement.classList.add("pjx-loading--page");
  });

  document.addEventListener("pjx:page-loading-end", function () {
    document.documentElement.classList.remove("pjx-loading--page");
  });
})();
