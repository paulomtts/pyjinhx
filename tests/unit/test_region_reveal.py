from pyjinhx.builtins import PJXTab, PJXTabGroup, PJXTabList, PJXTabPanel


def test_tab_group_regions_and_label():
    html = str(PJXTabGroup(
        id="tg",
        content=(
            str(PJXTabList(label="Abas", content=(
                str(PJXTab(id="tg-t0", panel="tg-p0", selected=True, content="One").render())
                + str(PJXTab(id="tg-t1", panel="tg-p1", content="Two").render())
            )).render())
            + str(PJXTabPanel(id="tg-p0", tab="tg-t0", content="1").render())
            + str(PJXTabPanel(id="tg-p1", tab="tg-t1", content="2").render())
        ),
    ).render())
    assert html.count("data-pjx-region") >= 2
    assert 'aria-label="Abas"' in html
