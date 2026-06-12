from pyjinhx.builtins import PJXLazyPanel, PJXRegionLoader, PJXSpinner


def test_lazy_panel_when_viewport_default():
    html = str(PJXLazyPanel(id="lp", url="/x").render())
    assert 'hx-trigger="revealed"' in html


def test_lazy_panel_when_reveal():
    html = str(PJXLazyPanel(id="lp", url="/x", when="reveal").render())
    assert 'hx-trigger="pjx:reveal from:closest [data-pjx-region] once"' in html


def test_lazy_panel_when_load():
    html = str(PJXLazyPanel(id="lp", url="/x", when="load").render())
    assert 'hx-trigger="load"' in html


def test_lazy_panel_raw_trigger_wins():
    html = str(PJXLazyPanel(id="lp", url="/x", when="reveal", trigger="click once").render())
    assert 'hx-trigger="click once"' in html


def test_region_loader_props():
    html = str(PJXRegionLoader(id="lo", aria_label="Carregando", class_name="mine").render())
    assert 'aria-label="Carregando"' in html and "pjx-region-loader mine" in html


def test_spinner_contract():
    html = str(PJXSpinner(id="s", class_name="htmx-indicator", extra_attrs={"data-k": "v"}).render())
    assert "htmx-indicator" in html and 'data-k="v"' in html
