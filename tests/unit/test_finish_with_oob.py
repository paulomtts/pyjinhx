from markupsafe import Markup

from pyjinhx.reactive import _mounted_ids_in


def test_mounted_ids_extracts_double_quoted_markers():
    html = '<div data-pjx-id="counter"></div><span data-pjx-id="clear-btn"></span>'
    assert _mounted_ids_in(html) == {"counter", "clear-btn"}


def test_mounted_ids_empty_on_plain_html():
    assert _mounted_ids_in("<div>no markers</div>") == set()


def test_mounted_ids_accepts_markup():
    assert _mounted_ids_in(Markup('<div data-pjx-id="x"></div>')) == {"x"}
