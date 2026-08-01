"""The htmx:configRequest listener that stamps the three manifest headers."""

from __future__ import annotations

import json

FIRE_EVENT = """
    () => {
      const detail = { headers: {}, elt: document.getElementById('btn') };
      document.body.dispatchEvent(
        new CustomEvent('htmx:configRequest', { detail, bubbles: true })
      );
      return detail.headers;
    }
"""

PAGE = (
    '<div data-pjx-id="a1" data-pjx-type="Card" data-pjx-hash="h1">'
    '<style data-pjx-asset="card.css"></style>'
    '<button id="btn">go</button>'
    "</div>"
)


def test_config_request_sets_the_mounted_header(pjx_page):
    headers = pjx_page(PAGE).evaluate(FIRE_EVENT)
    assert json.loads(headers["X-PJX-Mounted"]) == [
        {"id": "a1", "type": "Card", "hash": "h1"}
    ]


def test_config_request_sets_the_assets_header(pjx_page):
    headers = pjx_page(PAGE).evaluate(FIRE_EVENT)
    assert json.loads(headers["X-PJX-Assets"]) == ["card.css"]


def test_config_request_sets_the_trigger_header(pjx_page):
    headers = pjx_page(PAGE).evaluate(FIRE_EVENT)
    assert json.loads(headers["X-PJX-Trigger"]) == {"id": "a1"}


def test_config_request_omits_the_trigger_header_outside_a_region(pjx_page):
    headers = pjx_page('<button id="btn">go</button>').evaluate(FIRE_EVENT)
    assert "X-PJX-Trigger" not in headers
    assert json.loads(headers["X-PJX-Mounted"]) == []
