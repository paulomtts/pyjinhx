from pyjinhx.builtins import PJXLazyPanel, PJXSkeleton


def test_lazy_panel_default_render():
    html = str(PJXLazyPanel(id="lp-comments", url="/posts/42/comments").render())

    assert 'id="lp-comments"' in html
    assert 'hx-get="/posts/42/comments"' in html
    assert 'hx-trigger="revealed"' in html
    assert 'hx-swap="outerHTML"' in html


def test_lazy_panel_custom_trigger_and_swap():
    html = str(
        PJXLazyPanel(
            id="lp-tab",
            url="/tabs/activity",
            trigger="click once",
            swap="innerHTML",
        ).render()
    )

    assert 'hx-trigger="click once"' in html
    assert 'hx-swap="innerHTML"' in html


def test_lazy_panel_children_render_as_placeholder():
    html = str(
        PJXLazyPanel(
            id="lp-feed",
            url="/feed",
            content=PJXSkeleton(id="lp-feed-skel"),
        ).render()
    )

    assert 'hx-get="/feed"' in html
    assert 'id="lp-feed-skel"' in html
    assert html.index('hx-get="/feed"') < html.index('id="lp-feed-skel"')
