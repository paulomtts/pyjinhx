from pyjinhx.builtins import PJXLazyLoad, PJXSkeleton


def test_lazy_load_default_render():
    html = str(PJXLazyLoad(id="lp-comments", url="/posts/42/comments").render())
    assert html.lstrip().startswith("<div")
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
    assert html.lstrip().startswith("<tr")
    assert 'hx-get="/rows?cursor=20"' in html
    assert 'hx-trigger="revealed"' in html


def test_lazy_load_tag_li_renders_li_root():
    assert str(PJXLazyLoad(id="s", url="/x", tag="li").render()).lstrip().startswith("<li")


def test_lazy_load_default_tag_is_div():
    assert str(PJXLazyLoad(id="s", url="/x").render()).lstrip().startswith("<div")


def test_lazy_load_extra_attrs_inject_on_dynamic_root():
    html = str(PJXLazyLoad(id="s", url="/x", tag="tr", extra_attrs={"data-k": "v"}).render())
    assert html.lstrip().startswith("<tr")
    assert 'data-k="v"' in html
