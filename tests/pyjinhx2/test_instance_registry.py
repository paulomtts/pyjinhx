"""Tests for the minimal request-scoped instance registry (ADR 0009)."""

import pytest

from pyjinhx2.registry import make_key, resolve
from pyjinhx2.segments import RenderedLevel
from pyjinhx2.session import _instances, get_instances, request_scope


def test_make_key_joins_type_and_id_with_underscore():
    assert make_key("PJXButton", "btn1") == "PJXButton_btn1"
    assert make_key("Card", "42") == "Card_42"
    assert make_key("", "") == "_"
