import re

from pyjinhx.builtins import Popover, PopoverPanel, PopoverTrigger


def _markup(html: str, selector: str) -> str:
    """Slice out the first element matching a CSS-like start-tag prefix, stripping inlined assets."""
    m = re.search(r"(<" + selector + r"[\s\S]*?</" + selector.split(r"\b")[0] + r">)", html)
    return m.group(1) if m else html


def _popover_el(html: str) -> str:
    m = re.search(r'(<div[^>]*class="px-popover[\s\S]*?</div>)', html)
    return m.group(1) if m else html


def test_popover_root_wiring():
    html = str(Popover(id="p", content="x").render())
    el = _popover_el(html)
    assert 'class="px-popover"' in el
    assert "data-px-popover" in el


def test_popover_align_end():
    html = str(Popover(id="p", content="x", align="end").render())
    el = _popover_el(html)
    assert "px-popover--align-end" in el


def test_popover_headless_mode():
    html = str(Popover(id="p", content="x", behavior=False).render())
    el = _popover_el(html)
    assert "data-px-popover" not in el


def test_trigger_wiring_and_a11y():
    html = str(PopoverTrigger(id="t", content="Open", role="menu").render())
    assert "data-px-toggle" in html
    assert 'aria-expanded="false"' in html
    assert 'aria-haspopup="menu"' in html
    assert 'type="button"' in html


def test_trigger_div_mode_keyboard():
    html = str(PopoverTrigger(id="t", content="Open", tag="div").render())
    assert "<div" in html and 'role="button"' in html and 'tabindex="0"' in html


def test_panel_hidden_and_marker():
    html = str(PopoverPanel(id="pp", content="Body", role="menu").render())
    assert "hidden" in html
    assert "data-px-popover-panel" in html
    assert 'role="menu"' in html


def test_panel_as_form():
    html = str(PopoverPanel(id="pp", content="Body", as_form=True).render())
    assert html.strip().startswith("<form")
