"""PJXPaginator — v0.x windowing + markup parity on the v2 engine."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.pjx_paginator import PJXPaginator

URL = "/u?page={page}"


def _shape(pag: PJXPaginator) -> list[str]:
    """Compact string view of ``items`` for readable assertions."""
    out: list[str] = []
    for item in pag.items:
        kind = item["kind"]
        if kind == "ellipsis":
            out.append("...")
        elif kind == "current":
            out.append(f"[{item['number']}]")
        elif kind == "page":
            out.append(str(item["number"]))
        else:
            out.append(("!" if item["disabled"] else "") + item["variant"])
    return out


def _bare(**kwargs) -> PJXPaginator:
    """Paginator with the prev/next and first/last controls switched off."""
    base = {"id": "p1", "url": URL, "prev_next": False, "first_last": False}
    base.update(kwargs)
    return PJXPaginator(**base)


class TestFields:
    def test_defaults(self):
        pag = PJXPaginator(id="p1", url=URL, page=1, total_pages=5)
        assert pag.target == ""
        assert pag.swap == "innerHTML"
        assert pag.push_url is False
        assert pag.siblings == 1
        assert pag.boundaries == 1
        assert pag.prev_next is True
        assert pag.first_last is False
        assert pag.prev_label == "Prev"
        assert pag.next_label == "Next"
        assert pag.first_label == "First"
        assert pag.last_label == "Last"
        assert pag.aria_label == "Pagination"
        assert pag.class_name == ""
        assert pag.extra_attrs == {}


class TestValidation:
    def test_url_without_page_placeholder_raises(self):
        with pytest.raises(ValidationError):
            PJXPaginator(id="p1", url="/users", page=1, total_pages=3)

    def test_total_pages_below_one_raises(self):
        with pytest.raises(ValidationError):
            PJXPaginator(id="p1", url=URL, page=1, total_pages=0)

    @pytest.mark.parametrize("field", ["siblings", "boundaries"])
    def test_negative_window_sizes_raise(self, field):
        with pytest.raises(ValidationError):
            PJXPaginator(id="p1", url=URL, page=1, total_pages=5, **{field: -1})  # type: ignore[arg-type]

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXPaginator(id="p1", url=URL, page=1, total_pages=5, bogus="x")  # type: ignore[call-arg]


class TestWindow:
    def test_single_page(self):
        assert _shape(_bare(page=1, total_pages=1)) == ["[1]"]

    def test_small_total_shows_every_page_without_ellipsis(self):
        assert _shape(_bare(page=2, total_pages=5)) == ["1", "[2]", "3", "4", "5"]

    def test_mid_range_has_ellipsis_on_both_sides(self):
        assert _shape(_bare(page=5, total_pages=20)) == [
            "1",
            "...",
            "4",
            "[5]",
            "6",
            "...",
            "20",
        ]

    def test_near_start_has_one_ellipsis(self):
        assert _shape(_bare(page=3, total_pages=20)) == [
            "1",
            "2",
            "[3]",
            "4",
            "...",
            "20",
        ]

    def test_gap_of_exactly_two_fills_the_number_instead_of_an_ellipsis(self):
        # a 1->3 gap of exactly 2 fills 2 rather than collapsing to an ellipsis
        assert _shape(_bare(page=3, total_pages=5, siblings=0)) == [
            "1",
            "2",
            "[3]",
            "4",
            "5",
        ]

    def test_page_above_range_clamps_to_total_pages(self):
        assert _shape(_bare(page=99, total_pages=5))[-1] == "[5]"

    def test_page_below_range_clamps_to_one(self):
        assert _shape(_bare(page=0, total_pages=5))[0] == "[1]"

    def test_window_method_returns_sorted_unique_pages(self):
        assert _bare(page=5, total_pages=20)._window() == [1, 4, 5, 6, 20]


class TestControls:
    def test_prev_disabled_on_first_page_next_enabled(self):
        pag = PJXPaginator(id="p1", url=URL, page=1, total_pages=10)
        assert _shape(pag) == ["!prev", "[1]", "2", "...", "10", "next"]

    def test_next_disabled_on_last_page(self):
        pag = PJXPaginator(id="p1", url=URL, page=10, total_pages=10)
        assert _shape(pag) == ["prev", "1", "...", "9", "[10]", "!next"]

    def test_single_page_disables_every_control(self):
        pag = PJXPaginator(id="p1", url=URL, page=1, total_pages=1, first_last=True)
        assert _shape(pag) == ["!first", "!prev", "[1]", "!next", "!last"]

    def test_first_last_wrap_the_prev_next_controls_when_enabled(self):
        shape = _shape(
            PJXPaginator(id="p1", url=URL, page=1, total_pages=10, first_last=True)
        )
        assert shape[0] == "!first"
        assert shape[1] == "!prev"
        assert shape[-1] == "last"
        assert shape[-2] == "next"

    def test_prev_next_false_omits_prev_and_next(self):
        shape = _shape(_bare(page=3, total_pages=10))
        assert "prev" not in shape
        assert "next" not in shape

    def test_disabled_control_has_no_href(self):
        pag = PJXPaginator(id="p1", url=URL, page=1, total_pages=5)
        prev = next(i for i in pag.items if i.get("variant") == "prev")
        assert prev["disabled"] is True
        assert "href" not in prev

    def test_enabled_controls_point_at_the_neighbouring_pages(self):
        pag = PJXPaginator(id="p1", url=URL, page=3, total_pages=5)
        prev = next(i for i in pag.items if i.get("variant") == "prev")
        nxt = next(i for i in pag.items if i.get("variant") == "next")
        assert prev["href"] == "/u?page=2"
        assert nxt["href"] == "/u?page=4"


class TestHref:
    def test_substitution_keeps_other_query_params(self):
        pag = _bare(url="/u?page={page}&sort=name", page=2, total_pages=5)
        page1 = next(i for i in pag.items if i["kind"] == "page" and i["number"] == 1)
        assert page1["href"] == "/u?page=1&sort=name"


class TestComputedFieldVisibility:
    def test_items_is_included_in_model_dump(self):
        """``build_context`` builds the Jinja context from ``model_dump()``,
        so ``items`` must appear there for the template to iterate it."""
        dumped = PJXPaginator(id="p1", url=URL, page=1, total_pages=3).model_dump()
        assert "items" in dumped
        assert dumped["items"][1]["kind"] == "current"


from pyjinhx.render import render  # noqa: E402
from pyjinhx.session import RenderSession  # noqa: E402


@pytest.fixture
def session():
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "p1", "url": URL, "page": 3, "total_pages": 10}
    base.update(kwargs)
    return render(PJXPaginator(**base), session)


class TestRender:
    def test_root_is_a_nav_with_the_aria_label_and_a_list(self, session):
        html = _html(session)
        assert html.startswith('<nav id="p1" class="pjx-paginator"')
        assert 'aria-label="Pagination"' in html
        assert '<ul class="pjx-paginator__list">' in html
        assert html.endswith("</ul></nav>")

    def test_custom_aria_label_is_used(self, session):
        assert 'aria-label="Pages"' in _html(session, aria_label="Pages")

    def test_current_page_is_a_span_with_aria_current(self, session):
        assert (
            '<span class="pjx-paginator__link pjx-paginator__link--current"'
            ' aria-current="page">3</span>'
        ) in _html(session)

    def test_other_pages_are_links_with_resolved_hrefs(self, session):
        assert 'href="/u?page=4"' in _html(session)

    def test_ellipsis_is_an_aria_hidden_span_with_the_entity_intact(self, session):
        html = _html(session, page=5, total_pages=20)
        assert (
            '<span class="pjx-paginator__ellipsis" aria-hidden="true">&hellip;</span>'
        ) in html

    def test_disabled_control_is_a_span_with_aria_disabled_and_no_href(self, session):
        html = _html(session, page=1, total_pages=10)
        assert ("pjx-paginator__control--prev pjx-paginator__control--disabled") in html
        assert 'aria-disabled="true"' in html

    def test_class_name_is_appended_to_the_root_class(self, session):
        assert 'class="pjx-paginator compact"' in _html(session, class_name="compact")

    def test_extra_attrs_surface_on_the_root_nav(self, session):
        html = _html(session, extra_attrs={"data-testid": "pager"})
        assert 'data-testid="pager"' in html
        assert html.index('data-testid="pager"') < html.index("<ul")


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXPaginator.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_paginator.css"
        assert css[0].is_file()


class TestHtmx:
    def test_no_hx_attributes_when_target_is_unset(self, session):
        html = _html(session)
        assert "hx-get" not in html
        assert "hx-target" not in html
        assert "hx-swap" not in html
        assert "hx-push-url" not in html

    def test_target_adds_hx_get_target_and_swap_to_page_links(self, session):
        html = _html(session, target="#tbl", swap="outerHTML")
        assert 'hx-get="/u?page=4"' in html
        assert 'hx-target="#tbl"' in html
        assert 'hx-swap="outerHTML"' in html

    def test_default_swap_is_inner_html(self, session):
        assert 'hx-swap="innerHTML"' in _html(session, target="#tbl")

    def test_push_url_is_off_by_default(self, session):
        assert "hx-push-url" not in _html(session, target="#tbl")

    def test_push_url_adds_hx_push_url_when_target_is_set(self, session):
        assert 'hx-push-url="true"' in _html(session, target="#tbl", push_url=True)

    def test_push_url_alone_emits_nothing_without_a_target(self, session):
        assert "hx-push-url" not in _html(session, push_url=True)

    def test_enabled_controls_also_get_hx_attributes(self, session):
        html = _html(session, target="#tbl")
        assert (
            'hx-get="/u?page=2" hx-target="#tbl" hx-swap="innerHTML">Prev</a>' in html
        )

    def test_disabled_controls_get_no_hx_attributes(self, session):
        html = _html(session, page=1, total_pages=10, target="#tbl")
        disabled_span = html[html.index("pjx-paginator__control--disabled") :]
        assert "hx-get" not in disabled_span[: disabled_span.index("</span>")]
