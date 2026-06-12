from pyjinhx.builtins import PJXToastHost


def test_toast_host_markers_and_config():
    html = str(PJXToastHost(id="th", position="top-right", timeout=2500,
                         dismiss_label="Fechar", event_name="toast").render())
    assert "data-pjx-toast-host" in html
    assert 'data-event-name="toast"' in html
    assert 'data-timeout="2500"' in html
    assert 'data-dismiss-label="Fechar"' in html
    assert "pjx-toast-host--top-right" in html
    assert 'aria-live="polite"' in html


def test_toast_host_defaults():
    html = str(PJXToastHost(id="th").render())
    assert 'data-event-name="pjx:toast"' in html
    assert "pjx-toast-host--bottom-right" in html
