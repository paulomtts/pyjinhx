"""Unit tests for the ``{#def ... #}`` header parser.

Parsing only — building a model class from the parsed spec belongs to #376,
so nothing here imports pydantic or pyjinhx2.component.
"""

from typing import Any

import pytest

from pyjinhx2.props_header import parse_props_header


def test_source_without_a_header_returns_none():
    """No header is the common case, not an error — most templates are strict."""
    assert parse_props_header("<div>hello</div>") is None


def test_header_with_no_props_returns_an_empty_list():
    """An empty header still declares the template classless, with zero props."""
    assert parse_props_header("{#def #}<div></div>") == []
