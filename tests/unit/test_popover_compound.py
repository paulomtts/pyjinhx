import re

from pyjinhx.builtins import PJXPopover, PJXPopoverPanel, PJXPopoverTrigger


def _popover_el(html: str) -> str:
    m = re.search(r'(<div[^>]*class="pjx-popover[\s\S]*?</div>)', html)
    return m.group(1) if m else html


def test_popover_root_wiring():
    html = str(PJXPopover(id="p", content="x").render())
    el = _popover_el(html)
    assert 'class="pjx-popover"' in el
    assert "data-pjx-popover" in el


def test_popover_align_end():
    html = str(PJXPopover(id="p", content="x", align="end").render())
    el = _popover_el(html)
    assert "pjx-popover--align-end" in el


def test_popover_headless_mode():
    html = str(PJXPopover(id="p", content="x", behavior=False).render())
    el = _popover_el(html)
    assert "data-pjx-popover" not in el


def test_popover_panel_headless_mode():
    html = str(PJXPopoverPanel(id="pp", content="x", behavior=False).render())
    assert "data-pjx-popover-panel" not in html


def test_trigger_wiring_and_a11y():
    html = str(PJXPopoverTrigger(id="t", content="Open", role="menu").render())
    assert "data-pjx-toggle" in html
    assert 'aria-expanded="false"' in html
    assert 'aria-haspopup="menu"' in html
    assert 'type="button"' in html


def test_trigger_div_mode_keyboard():
    html = str(PJXPopoverTrigger(id="t", content="Open", tag="div").render())
    assert "<div" in html and 'role="button"' in html and 'tabindex="0"' in html


def test_panel_hidden_and_marker():
    html = str(PJXPopoverPanel(id="pp", content="Body", role="menu").render())
    assert "hidden" in html
    assert "data-pjx-popover-panel" in html
    assert 'role="menu"' in html


def test_panel_as_form():
    html = str(PJXPopoverPanel(id="pp", content="Body", as_form=True).render())
    assert html.strip().startswith("<form")
