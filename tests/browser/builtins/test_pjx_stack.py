"""PJXStack lays its content out as a flex row or column spaced by the theme's spacing scale."""

from collections.abc import Iterator

import pytest

from pyjinhx.builtins.pjx_stack import PJXStack
from pyjinhx.client.inject import inject_runtime
from pyjinhx.config import PjxSettings, configure_pyjinhx, shutdown_pyjinhx
from pyjinhx.rendering.pipeline import render
from pyjinhx.rendering.session import RenderSession, accumulate_assets

CHILD = '<div class="child" style="height: 10px"></div>'


def _style(page, element_id: str, prop: str) -> str:
    return page.evaluate(
        f"getComputedStyle(document.getElementById('{element_id}'))"
        f".getPropertyValue('{prop}')"
    )


def _render_with_assets(stack: PJXStack, *, themed: bool) -> str:
    """Render stack with its stylesheet (and the theme, if on) appended."""
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    if themed:
        inject_runtime(session)
    return render(stack, session)


def test_unthemed_stack_uses_the_literal_fallback_gap(page):
    html = _render_with_assets(PJXStack(id="s", content=CHILD * 3), themed=False)
    assert "pjx-theme" not in html
    page.set_content(f"<html><body>{html}</body></html>")
    assert _style(page, "s", "display") == "flex"
    assert _style(page, "s", "flex-direction") == "column"
    assert _style(page, "s", "row-gap") == "12px"
    first, second = page.evaluate(
        "[...document.querySelectorAll('#s > .child')].slice(0, 2)"
        ".map(e => e.getBoundingClientRect()).map(r => [r.top, r.bottom])"
    )
    assert second[0] == first[1] + 12


@pytest.fixture
def themed() -> Iterator[None]:
    configure_pyjinhx(PjxSettings(theme="default"))
    # Teardown runs even when the test fails, so the theme never leaks into a
    # later test that expects the default settings.
    yield
    shutdown_pyjinhx()


def test_themed_stack_follows_the_spacing_token(themed, page):
    stack = PJXStack(
        id="s",
        direction="horizontal",
        gap="8",
        justify="between",
        wrap=True,
        content=CHILD * 3,
    )
    html = _render_with_assets(stack, themed=True)
    assert '<style id="pjx-theme">' in html
    page.set_content(f'<html><body><div id="w">{html}</div></body></html>')
    assert _style(page, "s", "flex-direction") == "row"
    assert _style(page, "s", "column-gap") == "32px"
    assert _style(page, "s", "justify-content") == "space-between"
    assert _style(page, "s", "flex-wrap") == "wrap"
    page.evaluate(
        "document.getElementById('w').style.setProperty('--pjx-space-8', '5px')"
    )
    assert _style(page, "s", "column-gap") == "5px"
