"""Unit tests for the tier-2 (non-reactive) render-cache key.

The classes here carry hand-built descriptors pointing at a tmp-path template
so a test can change the template's mtime without touching a real fixture
file. Each test attaches the descriptor it needs, so the class-level
attribute never carries state between tests.
"""

import os
from pathlib import Path

import pytest

from pyjinhx._component import BaseComponent
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.render_cache import render_cache_key


class _KeyPlain(BaseComponent):
    label: str = "hi"


class _KeyOther(BaseComponent):
    label: str = "hi"


def _attach(
    cls: type[BaseComponent],
    template_path: Path,
    *,
    slot_fields: frozenset[str] = frozenset(),
    children_field: str | None = None,
) -> None:
    cls.__pjx_descriptor__ = ClassDescriptor(
        template_path=template_path,
        slot_fields=slot_fields,
        children_field=children_field,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


@pytest.fixture
def template(tmp_path: Path) -> Path:
    path = tmp_path / "key_template.html"
    path.write_text("<div>{{ label }}</div>", encoding="utf-8")
    return path


def test_same_class_same_props_same_template_gives_the_same_key(template: Path):
    _attach(_KeyPlain, template)
    first = render_cache_key(_KeyPlain(id="a", label="hi"))
    second = render_cache_key(_KeyPlain(id="a", label="hi"))
    assert first == second


def test_a_differing_prop_value_gives_a_different_key(template: Path):
    _attach(_KeyPlain, template)
    assert render_cache_key(_KeyPlain(id="a", label="hi")) != render_cache_key(
        _KeyPlain(id="a", label="bye")
    )


def test_a_different_class_with_identical_props_gives_a_different_key(template: Path):
    _attach(_KeyPlain, template)
    _attach(_KeyOther, template)
    assert render_cache_key(_KeyPlain(id="a", label="hi")) != render_cache_key(
        _KeyOther(id="a", label="hi")
    )


def test_a_changed_template_mtime_gives_a_different_key(template: Path):
    _attach(_KeyPlain, template)
    before = render_cache_key(_KeyPlain(id="a", label="hi"))
    os.utime(template, (1_000_000_000, 1_000_000_000))
    assert render_cache_key(_KeyPlain(id="a", label="hi")) != before


def test_an_unreadable_template_propagates_the_stat_error(tmp_path: Path):
    _attach(_KeyPlain, tmp_path / "gone.html")
    with pytest.raises(FileNotFoundError):
        render_cache_key(_KeyPlain(id="a", label="hi"))
