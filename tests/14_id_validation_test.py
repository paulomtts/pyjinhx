import pytest

from tests.ui.unified_component import UnifiedComponent


def test_invalid_empty_id():
    with pytest.raises(ValueError, match="ID is required"):
        UnifiedComponent(id="", text="Test")


def test_invalid_none_id():
    with pytest.raises(ValueError, match="ID is required"):
        UnifiedComponent(id=None, text="Test")

