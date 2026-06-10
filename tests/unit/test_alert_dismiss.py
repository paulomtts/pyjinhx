from pyjinhx.builtins import Alert


def test_alert_dismiss_props_and_wiring():
    html = str(Alert(id="a", body="x", dismissible=True, dismiss_label="Fechar",
                     class_name="mine", extra_attrs={"data-k": "v"}).render())
    assert 'aria-label="Fechar"' in html
    assert "data-px-close" in html
    assert "onclick" not in html
    assert 'data-k="v"' in html
    assert "px-alert--info mine" in html
