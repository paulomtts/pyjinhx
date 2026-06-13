from pyjinhx.builtins import PJXPanel, PJXPanelTrigger, PJXTabGroup


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
    html = str(PJXTabGroup(id="tg", tabs={"One": "1", "Two": "2"}, tabs_label="Abas").render())
    assert html.count("data-pjx-region") >= 2
    assert 'aria-label="Abas"' in html
