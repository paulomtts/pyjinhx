from markupsafe import Markup

from pyjinhx.client import PJX_MOUNTED_HEADER, client_script
from pyjinhx.utils import read_client_runtime


def test_header_constant():
    assert PJX_MOUNTED_HEADER == "X-PJX-Mounted"


def test_runtime_source_reports_manifest_header():
    source = read_client_runtime()
    assert "htmx:configRequest" in source
    assert "X-PJX-Mounted" in source
    assert "X-PJX-Assets" in source
    assert "data-pjx-id" in source


def test_runtime_reports_asset_tokens():
    source = read_client_runtime()
    assert "data-pjx-asset" in source


def test_client_script_wraps_runtime_in_script_tag():
    script = client_script()
    assert isinstance(script, Markup)
    assert script.startswith("<script>")
    assert script.endswith("</script>")
    assert "htmx:configRequest" in script


def test_runtime_warns_when_htmx_missing():
    # Reactivity silently no-ops without htmx; pjx.js must make that loud.
    source = read_client_runtime()
    assert "window.htmx" in source
    assert "console.error" in source
