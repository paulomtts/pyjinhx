import re

from tests.ui.unified_component import UnifiedComponent


def test_empty_id_autogenerates():
    comp = UnifiedComponent(id="", text="Test")
    assert re.fullmatch(r"px-\d+", comp.id)


def test_none_id_autogenerates():
    comp = UnifiedComponent(id=None, text="Test")
    assert re.fullmatch(r"px-\d+", comp.id)
