(function () {
  window.pjx = window.pjx || {};
  var rootEl = document.documentElement;
  if (rootEl.dataset.pjxCarouselBound) return;
  rootEl.dataset.pjxCarouselBound = "1";

  function fire(el, name, detail, cancelable) {
    return el.dispatchEvent(new CustomEvent(name, { bubbles: true, cancelable: !!cancelable, detail: detail || {} }));
  }

  function slidesOf(carousel) {
    return Array.prototype.slice.call(carousel.querySelectorAll("[data-pjx-carousel-slide]"));
  }

  function trackOf(carousel) { return carousel.querySelector(".pjx-carousel__track"); }

  function currentIndex(carousel) {
    var slides = slidesOf(carousel);
    for (var i = 0; i < slides.length; i++) {
      if (slides[i].classList.contains("pjx-carousel__slide--active")) return i;
    }
    return 0;
  }

  function select(carousel, index, reason, silent) {
    var slides = slidesOf(carousel);
    if (!slides.length) return false;
    var loop = carousel.hasAttribute("data-pjx-carousel-loop");
    var clamped = loop ? ((index % slides.length) + slides.length) % slides.length
                        : Math.max(0, Math.min(index, slides.length - 1));
    var detail = { index: clamped, reason: reason || "api" };
    if (!silent && !fire(carousel, "pjx:carousel:before-change", detail, true)) return false;
    slides.forEach(function (slide, i) {
      var active = i === clamped;
      slide.classList.toggle("pjx-carousel__slide--active", active);
      if (active) { slide.removeAttribute("aria-hidden"); slide.removeAttribute("inert"); }
      else { slide.setAttribute("aria-hidden", "true"); slide.setAttribute("inert", ""); }
      slide.setAttribute("aria-label", (slide.dataset.pjxCarouselLabel ? slide.dataset.pjxCarouselLabel + " — " : "") + (i + 1) + " of " + slides.length);
    });
    carousel.style.setProperty("--pjx-carousel-offset", String(clamped));
    updateArrows(carousel, clamped, slides.length, loop);
    updateDots(carousel, clamped);
    if (!silent) fire(carousel, "pjx:carousel:change", detail);
    return true;
  }

  function updateArrows(carousel, index, count, loop) {
    var prev = carousel.querySelector("[data-pjx-carousel-prev]");
    var next = carousel.querySelector("[data-pjx-carousel-next]");
    if (prev) prev.toggleAttribute("aria-disabled", !loop && index === 0);
    if (next) next.toggleAttribute("aria-disabled", !loop && index === count - 1);
  }

  function buildDots(carousel) {
    var container = carousel.querySelector("[data-pjx-carousel-dots]");
    if (!container || container.dataset.pjxCarouselDotsBuilt) return;
    container.dataset.pjxCarouselDotsBuilt = "1";
    var slides = slidesOf(carousel);
    slides.forEach(function (_, i) {
      var dot = document.createElement("button");
      dot.type = "button";
      dot.className = "pjx-carousel__dot";
      dot.setAttribute("aria-label", "Go to slide " + (i + 1));
      dot.dataset.pjxCarouselDot = String(i);
      container.appendChild(dot);
    });
  }

  function updateDots(carousel, index) {
    var dots = carousel.querySelectorAll("[data-pjx-carousel-dot]");
    dots.forEach(function (dot, i) { dot.toggleAttribute("aria-current", i === index) || dot.setAttribute("aria-current", i === index ? "true" : "false"); });
  }

  var timers = new WeakMap();

  function stopAutoplay(carousel) {
    var t = timers.get(carousel);
    if (t) { clearInterval(t); timers.delete(carousel); }
    carousel.setAttribute("data-pjx-carousel-paused", "");
  }

  function startAutoplay(carousel) {
    if (!carousel.hasAttribute("data-pjx-carousel-autoplay")) return;
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (timers.get(carousel)) return;
    var interval = parseInt(carousel.getAttribute("data-pjx-carousel-interval"), 10) || 5000;
    var t = setInterval(function () {
      select(carousel, currentIndex(carousel) + 1, "autoplay");
    }, interval);
    timers.set(carousel, t);
    carousel.removeAttribute("data-pjx-carousel-paused");
  }

  function initCarousel(carousel) {
    if (carousel.dataset.pjxCarouselInit) return;
    carousel.dataset.pjxCarouselInit = "1";
    buildDots(carousel);
    select(carousel, 0, "api", true);
    if (carousel.hasAttribute("data-pjx-carousel-autoplay")) {
      startAutoplay(carousel);
      ["mouseenter", "focusin", "pointerdown"].forEach(function (evt) {
        carousel.addEventListener(evt, function () { stopAutoplay(carousel); });
      });
      ["mouseleave", "focusout"].forEach(function (evt) {
        carousel.addEventListener(evt, function () {
          if (!carousel.dataset.pjxCarouselUserPaused) startAutoplay(carousel);
        });
      });
      window.addEventListener("blur", function () { stopAutoplay(carousel); });
    }
  }

  document.addEventListener("click", function (e) {
    var carousel = e.target.closest && e.target.closest("[data-pjx-carousel]");
    if (!carousel) return;
    if (e.target.closest("[data-pjx-carousel-prev]")) { select(carousel, currentIndex(carousel) - 1, "arrow"); return; }
    if (e.target.closest("[data-pjx-carousel-next]")) { select(carousel, currentIndex(carousel) + 1, "arrow"); return; }
    var dot = e.target.closest("[data-pjx-carousel-dot]");
    if (dot) { select(carousel, parseInt(dot.dataset.pjxCarouselDot, 10), "dot"); return; }
    if (e.target.closest("[data-pjx-carousel-autoplay-toggle]")) {
      if (timers.get(carousel)) { carousel.dataset.pjxCarouselUserPaused = "1"; stopAutoplay(carousel); }
      else { delete carousel.dataset.pjxCarouselUserPaused; startAutoplay(carousel); }
    }
  });

  document.addEventListener("keydown", function (e) {
    var track = e.target.closest && e.target.closest(".pjx-carousel__track");
    if (!track) return;
    var carousel = track.closest("[data-pjx-carousel]");
    if (!carousel) return;
    if (e.key === "ArrowRight") { e.preventDefault(); select(carousel, currentIndex(carousel) + 1, "keyboard"); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); select(carousel, currentIndex(carousel) - 1, "keyboard"); }
  });

  var swipeStart = null;
  document.addEventListener("pointerdown", function (e) {
    var track = e.target.closest && e.target.closest(".pjx-carousel__track");
    if (!track) return;
    swipeStart = { track: track, x: e.clientX };
  });
  document.addEventListener("pointerup", function (e) {
    if (!swipeStart || swipeStart.track !== (e.target.closest && e.target.closest(".pjx-carousel__track"))) { swipeStart = null; return; }
    var dx = e.clientX - swipeStart.x;
    var carousel = swipeStart.track.closest("[data-pjx-carousel]");
    swipeStart = null;
    if (!carousel || Math.abs(dx) < 40) return;
    select(carousel, currentIndex(carousel) + (dx < 0 ? 1 : -1), "swipe");
  });

  function initAll(scope) {
    (scope && scope.querySelectorAll ? scope : document)
      .querySelectorAll("[data-pjx-carousel]").forEach(initCarousel);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { initAll(document); });
  } else { initAll(document); }
  document.addEventListener("htmx:afterSettle", function (e) { initAll((e.detail && e.detail.elt) || document); });
}());
