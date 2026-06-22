from pyjinhx.builtins import PJXPanel, PJXPanelTrigger, PJXTab, PJXTabGroup, PJXTabList, PJXTabPanel


def test_panel_panels_are_regions():
    html = str(PJXPanel(id="h", panels={"a": "<p>A</p>", "b": "<p>B</p>"}).render())
    assert html.count("data-pjx-region") >= 2


def test_panel_contract_fields():
    html = str(PJXPanel(id="h", panels={"a": "x"}, class_name="mine",
                     extra_attrs={"data-k": "v"}).render())
    assert 'class="pjx-panel mine"' in html and 'data-k="v"' in html


def test_panel_trigger_contract_fields():
    html = str(PJXPanelTrigger(id="t", panel_id="h", panel="a", content="A",
                            class_name="mine", extra_attrs={"data-k": "v"}).render())
    assert "pjx-panel-trigger mine" in html and 'data-k="v"' in html


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
