"""Tests for the stale {#def#} header warning.

A hand-written BaseComponent subclass should emit a one-time logger.warning
when its resolved template contains a {#def#} header (the header is silently
ignored by the engine because the class-based path overrides it).

Classless components and hand-written classes whose templates lack a header
must remain silent.

Fixture templates (co-located with this test file so Finder.get_class_directory
resolves them correctly):
  - stale_card.html    — has a {#def#} header (triggers warning for StaleCard)
  - stale_badge.html   — no header (silent for StaleBadge)
"""
import logging
import os

import pytest

from pyjinhx import Renderer
from pyjinhx.base import BaseComponent

# ---------------------------------------------------------------------------
# Module-level classes — defined here so inspect.getfile points to this file
# and Finder.get_class_directory returns the tests/unit/ directory (where the
# fixture templates live).
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(__file__)


class StaleCard(BaseComponent):
    """Hand-written class whose template has a {#def#} header."""
    title: str = "default"


class StaleBadge(BaseComponent):
    """Hand-written class whose template has NO {#def#} header."""
    text: str = "OK"


@pytest.fixture(autouse=True)
def isolate_renderer():
    """Point the default environment at tests/unit/ so templates are found."""
    Renderer.set_default_environment(_HERE)
    yield
    Renderer.set_default_environment(None)
    Renderer._default_renderers.clear()


@pytest.fixture(autouse=True)
def clear_stale_warning_set():
    """Reset the dedup set between tests so warnings are fresh."""
    from pyjinhx import renderer as renderer_mod
    renderer_mod._warned_stale_def_header.clear()
    yield
    renderer_mod._warned_stale_def_header.clear()


# ---------------------------------------------------------------------------
# Test 1: Hand-written class + {#def#} header → warns once, then deduplicates
# ---------------------------------------------------------------------------

def test_warns_once_for_hand_written_class_with_header(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        StaleCard(title="Hello").render()

    # Should have emitted exactly one warning mentioning the stale header
    stale_warnings = [r for r in caplog.records if "{#def#}" in r.message]
    assert len(stale_warnings) == 1, (
        f"Expected exactly 1 stale-header warning, got {len(stale_warnings)}: "
        f"{[r.message for r in stale_warnings]}"
    )
    assert "StaleCard" in stale_warnings[0].message

    # Second render must NOT emit another warning (dedup)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        StaleCard(title="World").render()

    second_stale = [r for r in caplog.records if "{#def#}" in r.message]
    assert len(second_stale) == 0, (
        f"Expected no second warning (dedup), got {len(second_stale)}"
    )


# ---------------------------------------------------------------------------
# Test 2: Classless component (header-only, _pjx_classless=True) → silent
# ---------------------------------------------------------------------------

def test_no_warning_for_classless_component(tmp_path, caplog):
    from pyjinhx.base import component

    comp_dir = tmp_path / "staleclassless"
    comp_dir.mkdir()
    (comp_dir / "staleclassless.html").write_text(
        "{#def label: str #}\n<span class=\"staleclassless\">{{ label }}</span>",
        encoding="utf-8",
    )

    Renderer.set_default_environment(str(tmp_path))

    StaleClassless = component("Staleclassless")
    # Verify it IS classless so the test is testing the right thing
    assert getattr(StaleClassless, "_pjx_classless", False) is True

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        StaleClassless(label="test").render()

    stale_warnings = [r for r in caplog.records if "{#def#}" in r.message]
    assert len(stale_warnings) == 0, (
        f"Classless component should not trigger stale-header warning, "
        f"got: {[r.message for r in stale_warnings]}"
    )


# ---------------------------------------------------------------------------
# Test 3: Hand-written class WITHOUT a {#def#} header → silent
# ---------------------------------------------------------------------------

def test_no_warning_for_hand_written_class_without_header(caplog):
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        StaleBadge(text="Active").render()

    stale_warnings = [r for r in caplog.records if "{#def#}" in r.message]
    assert len(stale_warnings) == 0, (
        f"No warning expected for class without header, "
        f"got: {[r.message for r in stale_warnings]}"
    )
