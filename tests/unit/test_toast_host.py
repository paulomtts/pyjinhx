from pyjinhx.builtins import ToastHost


def test_toast_host_markers_and_config():
    html = str(ToastHost(id="th", position="top-right", timeout=2500,
                         dismiss_label="Fechar", event_name="toast").render())
    assert "data-px-toast-host" in html
    assert 'data-event-name="toast"' in html
    assert 'data-timeout="2500"' in html
    assert 'data-dismiss-label="Fechar"' in html
    assert "px-toast-host--top-right" in html
    assert 'aria-live="polite"' in html


def test_toast_host_defaults():
    html = str(ToastHost(id="th").render())
    assert 'data-event-name="px:toast"' in html
    assert "px-toast-host--bottom-right" in html
