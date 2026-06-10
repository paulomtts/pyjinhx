from pyjinhx.builtins import Panel, PanelTrigger, TabGroup


def test_panel_panels_are_regions():
    html = str(Panel(id="h", panels={"a": "<p>A</p>", "b": "<p>B</p>"}).render())
    assert html.count("data-px-region") >= 2


def test_panel_contract_fields():
    html = str(Panel(id="h", panels={"a": "x"}, class_name="mine",
                     extra_attrs={"data-k": "v"}).render())
    assert 'class="px-panel mine"' in html and 'data-k="v"' in html


def test_panel_trigger_contract_fields():
    html = str(PanelTrigger(id="t", panel_id="h", panel="a", content="A",
                            class_name="mine", extra_attrs={"data-k": "v"}).render())
    assert "px-panel-trigger mine" in html and 'data-k="v"' in html


def test_tab_group_regions_and_label():
    html = str(TabGroup(id="tg", tabs={"One": "1", "Two": "2"}, tabs_label="Abas").render())
    assert html.count("data-px-region") >= 2
    assert 'aria-label="Abas"' in html
