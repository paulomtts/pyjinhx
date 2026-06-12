import pytest

from pyjinhx.builtins import (
    PJXAvatar, PJXBadge, PJXBreadcrumb, PJXCard, PJXDivider, PJXEmptyState, PJXProgress, PJXSkeleton, PJXTooltip,
)

SWEPT = [PJXAvatar, PJXBadge, PJXBreadcrumb, PJXCard, PJXDivider, PJXEmptyState, PJXProgress, PJXSkeleton, PJXTooltip]


def test_class_name_and_extra_attrs_render():
    html = str(PJXBadge(id="b", label="x", class_name="mine", extra_attrs={"data-k": "v"}).render())
    assert 'class="pjx-badge pjx-badge--neutral pjx-badge--md mine"' in html
    assert 'data-k="v"' in html
    assert 'id="b"' in html  # PJXBadge root gains an id attribute


def test_extra_attrs_rejects_breakout_values():
    # Both quote types make a value inexpressible — rejected at construction.
    with pytest.raises(ValueError):
        PJXBadge(id="b", label="x", extra_attrs={"data-k": "a\"b'c"})
    # A lone double quote is fine: emission switches to single quotes.
    html = str(PJXBadge(id="b", label="x", extra_attrs={"data-k": '" onmouseover="x'}).render())
    assert "data-k='\" onmouseover=\"x'" in html
    # < and > are spec-legal inside quoted attrs — must NOT be rejected
    badge = PJXBadge(id="b", label="x", extra_attrs={"x-show": "count > 3"})
    assert 'x-show="count &gt; 3"' in str(badge.render()) or 'x-show="count > 3"' in str(badge.render())


def test_extra_attrs_rejects_bad_names():
    with pytest.raises(ValueError):
        PJXBadge(id="b", label="x", extra_attrs={"data k": "v"})


def test_class_name_and_color_reject_quotes():
    with pytest.raises(ValueError):
        PJXBadge(id="b", label="x", class_name='mine" onmouseover="x')
    with pytest.raises(ValueError):
        PJXAvatar(id="a", initials="X", color='red" onmouseover="x')


def test_extra_attrs_allows_htmx_and_alpine_names():
    html = str(PJXBadge(id="b", label="x", extra_attrs={
        "hx-get": "/x", "data-k": "v", "@click": "open = !open",
        "x-on:click.prevent": "go()", "hx-on::after-swap": "init()",
        "aria-label": "ok",
    }).render())
    assert 'hx-get="/x"' in html
    assert '@click="open = !open"' in html
    assert 'data-k="v"' in html
    assert 'x-on:click.prevent="go()"' in html
    assert 'hx-on::after-swap="init()"' in html
    assert 'aria-label="ok"' in html


def test_avatar_color():
    html = str(PJXAvatar(id="a", initials="PM", color="#A0C080").render())
    assert "background:#A0C080" in html.replace(" ", "")


def test_breadcrumb_aria_label_prop():
    html = str(PJXBreadcrumb(id="bc", items=[("Home", "/")], aria_label="Caminho").render())
    assert 'aria-label="Caminho"' in html


def test_progress_loading_label_prop():
    html = str(PJXProgress(id="p", loading_label="Carregando").render())
    assert 'aria-label="Carregando"' in html
