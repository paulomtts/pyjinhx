from pyjinhx.builtins import PJXAlert


def test_alert_dismiss_props_and_wiring():
    html = str(PJXAlert(id="a", body="x", dismissible=True, dismiss_label="Fechar",
                     class_name="mine", extra_attrs={"data-k": "v"}).render())
    assert 'aria-label="Fechar"' in html
    assert "data-pjx-close" in html
    assert "onclick" not in html
    assert 'data-k="v"' in html
    assert "pjx-alert--info mine" in html
