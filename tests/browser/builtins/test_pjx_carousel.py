"""PJXCarousel: the stylesheet's transition timing, read from computed style in chromium."""

import pytest

from pyjinhx.builtins.pjx_carousel import PJXCarousel
from pyjinhx.client import read_pjx_theme_css


def _carousel_css() -> str:
    return PJXCarousel.__pjx_descriptor__.css_paths[0].read_text()


def _track_timing(page, *, theme: str = "", extra: str = "") -> dict[str, str]:
    """Load the carousel sheet (after an optional theme sheet) and read the track's transition."""
    page.set_content(
        f"<style>{theme}</style><style>{_carousel_css()}{extra}</style>"
        '<div class="pjx-carousel"><div class="pjx-carousel__track" id="t"></div></div>'
    )
    return page.evaluate(
        "(() => { const s = getComputedStyle(document.getElementById('t'));"
        " return {property: s.transitionProperty, duration: s.transitionDuration,"
        " delay: s.transitionDelay, easing: s.transitionTimingFunction}; })()"
    )


class TestAssets:
    @pytest.mark.parametrize("themed", [False, True], ids=["fallbacks", "themed"])
    def test_track_transition_has_no_delay(self, page, themed):
        page.emulate_media(reduced_motion="no-preference")
        theme = read_pjx_theme_css() if themed else ""
        assert _track_timing(page, theme=theme) == {
            "property": "transform",
            "duration": "0.25s",
            "delay": "0s",
            "easing": "cubic-bezier(0.2, 0, 0, 1)",
        }

    def test_track_does_not_animate_under_reduced_motion(self, page):
        page.emulate_media(reduced_motion="reduce")
        assert _track_timing(page)["duration"] == "0s"

    def test_app_override_sets_the_whole_timing(self, page):
        page.emulate_media(reduced_motion="no-preference")
        extra = ".pjx-carousel { --pjx-carousel-transition: 400ms linear; }"
        timing = _track_timing(page, extra=extra)
        assert (timing["duration"], timing["delay"], timing["easing"]) == (
            "0.4s",
            "0s",
            "linear",
        )
