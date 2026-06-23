"""PJXPaginator — windowing logic + markup."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins.ui.pjx_paginator.pjx_paginator import PJXPaginator


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _shape(pag):
    """Compact string view of items for readable assertions."""
    out = []
    for it in pag.items:
        k = it["kind"]
        if k == "ellipsis":
            out.append("…")
        elif k == "current":
            out.append(f"[{it['number']}]")
        elif k == "page":
            out.append(str(it["number"]))
        else:  # control
            out.append(("!" if it["disabled"] else "") + it["variant"])
    return out


URL = "/u?page={page}"


def _p(**kw):
    base = dict(url=URL, prev_next=False, first_last=False)
    base.update(kw)
    return PJXPaginator(**base)


def test_window_single_page():
    assert _shape(_p(page=1, total_pages=1)) == ["[1]"]


def test_window_mid_range_double_ellipsis():
    assert _shape(_p(page=5, total_pages=20)) == ["1", "…", "4", "[5]", "6", "…", "20"]


def test_window_near_start_one_ellipsis():
    assert _shape(_p(page=3, total_pages=20)) == ["1", "2", "[3]", "4", "…", "20"]


def test_window_single_gap_collapses_to_number():
    # the 3->5 gap of exactly 2 fills 4 instead of an ellipsis
    assert _shape(_p(page=2, total_pages=5)) == ["1", "[2]", "3", "4", "5"]


def test_page_clamped_above_range():
    # page above range clamps the current marker to total_pages
    pag = _p(page=99, total_pages=5)
    assert any(it["kind"] == "current" and it["number"] == 5 for it in pag.items)


def test_page_clamped_below_range():
    pag = _p(page=0, total_pages=5)
    assert any(it["kind"] == "current" and it["number"] == 1 for it in pag.items)


def test_controls_prev_next_enabled_and_disabled():
    # page 1 of 10: prev disabled, next enabled
    assert _shape(PJXPaginator(url=URL, page=1, total_pages=10)) == \
        ["!prev", "[1]", "2", "…", "10", "next"]
    # page 10 of 10: next disabled
    assert _shape(PJXPaginator(url=URL, page=10, total_pages=10)) == \
        ["prev", "1", "…", "9", "[10]", "!next"]


def test_controls_first_last_when_enabled():
    s = _shape(PJXPaginator(url=URL, page=1, total_pages=10, first_last=True))
    assert s[0] == "!first" and s[1] == "!prev"
    assert s[-1] == "last" and s[-2] == "next"


def test_href_substitution_keeps_other_query_params():
    pag = PJXPaginator(url="/u?page={page}&sort=name", page=2, total_pages=5, prev_next=False)
    page1 = next(it for it in pag.items if it.get("number") == 1 and it["kind"] == "page")
    assert page1["href"] == "/u?page=1&sort=name"


def test_disabled_control_has_no_href():
    pag = PJXPaginator(url=URL, page=1, total_pages=5)  # prev disabled
    prev = next(it for it in pag.items if it.get("variant") == "prev")
    assert prev["disabled"] is True and "href" not in prev


def test_enabled_control_has_href_to_target_page():
    pag = PJXPaginator(url=URL, page=3, total_pages=5)
    prev = next(it for it in pag.items if it.get("variant") == "prev")
    nxt = next(it for it in pag.items if it.get("variant") == "next")
    assert prev["href"] == "/u?page=2" and nxt["href"] == "/u?page=4"


def test_url_without_placeholder_raises():
    with pytest.raises(ValueError):
        PJXPaginator(url="/users", page=1, total_pages=3)


from pyjinhx.builtins import PJXPaginator as RegisteredPaginator  # noqa: E402


def _render(**kw):
    base = dict(url=URL, page=3, total_pages=10)
    base.update(kw)
    return str(PJXPaginator(**base).render())


def test_renders_nav_with_aria_label_and_list():
    html = _render()
    assert 'aria-label="Pagination"' in html and "pjx-paginator__list" in html
    assert "<nav" in html and "<ul" in html


def test_current_page_is_span_with_aria_current_not_link():
    html = _render(page=3, total_pages=10)
    assert 'aria-current="page"' in html
    assert '<span class="pjx-paginator__link pjx-paginator__link--current" aria-current="page">3</span>' in html


def test_other_pages_are_links_with_resolved_href():
    html = _render(page=3, total_pages=10)
    assert 'href="/u?page=4"' in html


def test_no_hx_attrs_without_target():
    assert "hx-get" not in _render(target="")


def test_hx_attrs_present_with_target():
    html = _render(target="#tbl", swap="outerHTML")
    assert 'hx-get="/u?page=4"' in html
    assert 'hx-target="#tbl"' in html
    assert 'hx-swap="outerHTML"' in html
    assert "hx-push-url" not in html  # off by default


def test_push_url_adds_hx_push_url_when_target_set():
    assert 'hx-push-url="true"' in _render(target="#tbl", push_url=True)


def test_ellipsis_is_aria_hidden_span():
    html = _render(page=5, total_pages=20)
    assert '<span class="pjx-paginator__ellipsis" aria-hidden="true">' in html


def test_disabled_control_is_span_aria_disabled_no_href():
    html = _render(page=1, total_pages=10)  # prev disabled
    assert 'pjx-paginator__control--prev pjx-paginator__control--disabled' in html
    assert 'aria-disabled="true"' in html


def test_registered_in_public_api():
    import pyjinhx.builtins as b
    assert "PJXPaginator" in b.__all__
    assert RegisteredPaginator is PJXPaginator
