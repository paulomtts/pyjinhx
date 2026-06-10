from pyjinhx.builtins import Drawer


def test_drawer_contract_and_lifecycle_attrs():
    html = str(Drawer(
        id="d1", title="T", body="B",
        close_label="Fechar", class_name="wide",
        extra_attrs={"data-x": "1"},
        open_on_mount=True, remove_on_close=True,
    ).render())
    assert 'class="px-drawer px-drawer--right wide"' in html
    assert 'aria-label="Fechar"' in html
    assert 'data-x="1"' in html
    assert "data-px-open-on-mount" in html
    assert "data-px-remove-on-close" in html
    assert "data-px-close" in html
    assert "onclick" not in html
