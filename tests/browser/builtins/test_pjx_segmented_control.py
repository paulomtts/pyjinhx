"""PJXSegmentedControl: the stylesheet fallbacks, read from computed style in chromium.

The field and markup checks are in tests/unit/builtins/test_pjx_segmented_control.py.
"""

from pyjinhx.builtins.pjx_segmented_control import PJXSegmentedControl

SEGMENTED_CSS = PJXSegmentedControl.__pjx_descriptor__.css_paths[0].read_text(
    encoding="utf-8"
)


def _segment_style(page, element_id: str, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}'))"
        f".getPropertyValue('{prop}')"
    )


def test_segmented_control_defaults_use_light_fallbacks(page):
    page.set_content(
        f"<html><head><style>{SEGMENTED_CSS}</style></head><body>"
        '<div id="root" class="pjx-segmented-control">'
        '<label class="pjx-segmented-control__segment">'
        '<input class="pjx-segmented-control__input" type="radio" name="v" checked>'
        '<span id="on" class="pjx-segmented-control__text">On</span></label>'
        '<label class="pjx-segmented-control__segment">'
        '<input class="pjx-segmented-control__input" type="radio" name="v">'
        '<span id="off" class="pjx-segmented-control__text">Off</span></label>'
        "</div></body></html>"
    )
    assert _segment_style(page, "root", "background-color") == "rgb(250, 250, 250)"
    assert _segment_style(page, "root", "border-top-color") == "rgb(228, 228, 231)"
    assert _segment_style(page, "root", "padding-top") == "4px"
    assert _segment_style(page, "off", "color") == "rgb(82, 82, 91)"
    assert _segment_style(page, "on", "color") == "rgb(24, 24, 27)"
    assert _segment_style(page, "on", "background-color") == "rgb(255, 255, 255)"
    assert _segment_style(page, "on", "padding-left") == "12px"
    # radius minus padding must stay a valid length with token fallbacks.
    assert _segment_style(page, "on", "border-top-left-radius") == "9995px"
