import re

from pyjinhx.builtins import PJXLazyLoad, PJXSkeleton


def _root(html: str) -> str:
    """The lazy-load root opening tag — the component now ships co-located
    CSS/JS, so ``.render()`` wraps the markup in ``<style>``/``<script>``."""
    match = re.search(r"<(?:div|tr|li)[^>]*\bpjx-lazy-load\b[^>]*>", html)
    assert match, html
    return match.group(0)


def test_lazy_load_default_render():
    html = str(PJXLazyLoad(id="lp-comments", url="/posts/42/comments").render())
    assert _root(html).startswith("<div")
    assert 'id="lp-comments"' in html
    assert "pjx-lazy-load" in html
    assert 'hx-get="/posts/42/comments"' in html
    assert 'hx-trigger="revealed"' in html
    assert 'hx-swap="outerHTML"' in html


def test_lazy_load_custom_trigger_and_swap():
    html = str(
        PJXLazyLoad(id="lp-tab", url="/tabs/activity", trigger="click once", swap="innerHTML").render()
    )
    assert 'hx-trigger="click once"' in html
    assert 'hx-swap="innerHTML"' in html


def test_lazy_load_children_render_as_placeholder():
    html = str(PJXLazyLoad(id="lp-feed", url="/feed", content=PJXSkeleton(id="lp-feed-skel")).render())
    assert 'hx-get="/feed"' in html
    assert 'id="lp-feed-skel"' in html
    assert html.index('hx-get="/feed"') < html.index('id="lp-feed-skel"')


def test_lazy_load_tag_tr_renders_tr_root():
    html = str(PJXLazyLoad(id="s", url="/rows?cursor=20", tag="tr").render())
    assert _root(html).startswith("<tr")
    assert 'hx-get="/rows?cursor=20"' in html
    assert 'hx-trigger="revealed"' in html


def test_lazy_load_tag_li_renders_li_root():
    assert _root(str(PJXLazyLoad(id="s", url="/x", tag="li").render())).startswith("<li")


def test_lazy_load_default_tag_is_div():
    assert _root(str(PJXLazyLoad(id="s", url="/x").render())).startswith("<div")


def test_lazy_load_extra_attrs_inject_on_dynamic_root():
    html = str(PJXLazyLoad(id="s", url="/x", tag="tr", extra_attrs={"data-k": "v"}).render())
    assert _root(html).startswith("<tr")
    assert 'data-k="v"' in _root(html)


# --- terminal failure path (#191) ------------------------------------------


def test_lazy_load_carries_error_marker_and_default_text():
    """The driver scopes on the marker and reads its default message from the
    element, so every lazy load can show an error instead of spinning forever."""
    html = str(PJXLazyLoad(id="s", url="/x").render())
    assert "data-pjx-lazy-load" in html
    assert 'data-pjx-error-text="Failed to load."' in html


def test_lazy_load_custom_error_text():
    html = str(PJXLazyLoad(id="s", url="/x", error_text="Could not load comments").render())
    assert 'data-pjx-error-text="Could not load comments"' in html


def test_lazy_load_error_slot_renders_raw_in_template():
    """A custom error slot rides in an inert <template> the driver reveals on
    failure; it must render raw (Slot), not HTML-escaped."""
    html = str(PJXLazyLoad(id="s", url="/x", error="<p>Boom</p>").render())
    assert "<template data-pjx-lazy-error><p>Boom</p></template>" in html


def test_lazy_load_without_error_slot_omits_template():
    # The driver references the selector ``template[data-pjx-lazy-error]``, so
    # assert the actual <template> element is absent, not the bare token.
    html = str(PJXLazyLoad(id="s", url="/x").render())
    assert "<template data-pjx-lazy-error" not in html
