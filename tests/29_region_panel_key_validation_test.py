import pytest

from pyjinhx.builtins import Region, RegionTrigger


def test_region_rejects_invalid_panel_key():
    with pytest.raises(ValueError, match="panel key"):
        Region(id="r1", panels={"bad key": "x"})


def test_region_trigger_rejects_invalid_panel_key():
    with pytest.raises(ValueError, match="panel key"):
        RegionTrigger(id="t1", region_id="r1", panel="bad key", label="x")


def test_region_render_smoke():
    html = str(
        Region(
            id="r-smoke",
            panels={"a": "<p>One</p>", "b": "<p>Two</p>"},
        ).render()
    )
    assert 'class="px-region"' in html
    assert 'data-px-region-panel="a"' in html
    assert 'id="r-smoke-panel-a"' in html


def test_region_trigger_render_smoke():
    html = str(
        RegionTrigger(id="t-smoke", region_id="r-smoke", panel="a", label="Go").render()
    )
    assert 'class="px-region-trigger"' in html
    assert 'data-px-region="r-smoke"' in html
    assert 'aria-controls="r-smoke-panel-a"' in html
