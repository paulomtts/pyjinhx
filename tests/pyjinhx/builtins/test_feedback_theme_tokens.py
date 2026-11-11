"""Alert, notification, toast host and spinner default to theme tokens."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pyjinhx.client import read_pjx_theme_css

UI = Path(__file__).parents[3] / "pyjinhx" / "builtins" / "ui"
STATUSES = ("info", "success", "warning", "error")

# Copied from tests/pyjinhx/test_theme_tokens.py: the tests tree has no
# __init__.py files, so test modules cannot import each other reliably.
ROOT = re.compile(r"^:root \{(.*?)^\}", re.MULTILINE | re.DOTALL)
DECLARATION = re.compile(r"([\w-]+):\s*([^;]+);")
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

ALERT = "pjx_alert/pjx_alert.css"


def light(token: str) -> str:
    """Return token's value in the theme sheet's light :root block."""
    match = ROOT.search(read_pjx_theme_css())
    assert match is not None, f"token block not found: {ROOT.pattern}"
    return dict(DECLARATION.findall(match.group(1)))[token]


def read(path: str) -> str:
    return (UI / path).read_text(encoding="utf-8")


def rule_block(css: str, selector: str) -> str:
    """Return the body of the rule whose selector starts a line, comments removed."""
    css = COMMENT.sub("", css)
    pattern = rf"^{re.escape(selector)}\s*\{{([^}}]*)\}}"
    match = re.search(pattern, css, re.MULTILINE)
    assert match is not None, f"no {selector} rule"
    return match.group(1)


def declared(css: str, selector: str, prop: str) -> str:
    """Return prop's value inside selector's rule, whitespace collapsed."""
    block = rule_block(css, selector)
    match = re.search(rf"(?<![\w-]){re.escape(prop)}:\s*([^;]+);", block)
    assert match is not None, f"{selector} does not declare {prop}"
    return " ".join(match.group(1).split())


def test_declared_reads_the_named_rule_and_property():
    css = (
        ".a-b { color: red; }\n"
        ".a { border-color: blue;\n  /* color: green; */\n  color:   var(--x,\n"
        "    #fff); }\n"
    )
    assert declared(css, ".a", "color") == "var(--x, #fff)"
    assert declared(css, ".a", "border-color") == "blue"
    assert declared(css, ".a-b", "color") == "red"


@pytest.mark.parametrize("status", STATUSES)
def test_alert_variant_uses_the_status_palette(status):
    css = read(ALERT)
    selector = f".pjx-alert--{status}"
    for prop, role in (
        ("background", "subtle"),
        ("border-color", "border"),
        ("color", "text"),
    ):
        token = f"--pjx-color-{status}-{role}"
        assert declared(css, selector, prop) == f"var({token}, {light(token)})"


@pytest.mark.parametrize("status", STATUSES)
def test_alert_variant_mixes_no_colours_and_skips_brand(status):
    block = rule_block(read(ALERT), f".pjx-alert--{status}")
    assert "color-mix" not in block
    assert "--pjx-color-brand" not in block


def test_alert_padding_keeps_its_off_scale_vertical():
    assert (
        declared(read(ALERT), ":where(:root)", "--pjx-alert-padding")
        == "0.875rem var(--pjx-space-4, 1rem)"
    )


NOTIFICATION = "pjx_notification/pjx_notification.css"


def test_notification_sits_on_the_notification_layer():
    assert (
        declared(read(NOTIFICATION), ":where(:root)", "--pjx-notification-z")
        == f"var(--pjx-z-notification, {light('--pjx-z-notification')})"
    )


def test_notification_padding_gives_every_step_a_fallback():
    css = read(NOTIFICATION)
    assert declared(css, ":where(:root)", "--pjx-notification-padding") == (
        "var(--pjx-space-4, 1rem) var(--pjx-space-4, 1rem) "
        "var(--pjx-space-4, 1rem) var(--pjx-space-5, 1.25rem)"
    )


TOAST = "pjx_toast_host/pjx_toast_host.css"


def test_toast_sits_on_the_toast_layer():
    # 600: above notifications (500), below the page loader (1000).
    assert (
        declared(read(TOAST), ":where(:root)", "--pjx-toast-z")
        == f"var(--pjx-z-toast, {light('--pjx-z-toast')})"
    )


@pytest.mark.parametrize("status", STATUSES)
def test_toast_status_colour_follows_the_theme(status):
    token = f"--pjx-color-{status}"
    assert (
        declared(read(TOAST), ":where(:root)", f"--pjx-toast-{status}")
        == f"var({token}, {light(token)})"
    )


SPINNER = "pjx_spinner/pjx_spinner.css"


def test_spinner_accent_follows_the_brand():
    assert (
        declared(read(SPINNER), ":where(:root)", "--pjx-spinner-accent")
        == f"var(--pjx-color-brand, {light('--pjx-color-brand')})"
    )


def test_spinner_track_mixes_the_muted_text_with_its_fallback():
    muted = light("--pjx-color-text-muted")
    assert declared(read(SPINNER), ":where(:root)", "--pjx-spinner-track") == (
        f"color-mix(in srgb, var(--pjx-color-text-muted, {muted}) 35%, transparent)"
    )
