import ast
import dataclasses
import inspect

import pytest

import pyjinhx2.segments
from pyjinhx2.segments import RenderedLevel


def make_level(
    segments: "list[str | RenderedLevel] | None" = None,
    root_span: tuple[int, int] = (0, 5),
    descriptor: object = None,
) -> "RenderedLevel":
    if segments is None:
        segments = ["<div>hi</div>"]
    return RenderedLevel(segments=segments, root_span=root_span, descriptor=descriptor)


class TestRenderedLevel:
    def test_holds_its_three_fields(self):
        level = make_level()
        assert level.segments == ["<div>hi</div>"]
        assert level.root_span == (0, 5)
        assert level.descriptor is None

    def test_segments_mutate_in_place(self):
        child = make_level(segments=["<button>go</button>"])
        parent = make_level(segments=["<div>", "PLACEHOLDER", "</div>"])
        parent.segments[1] = child
        assert parent.segments[1] is child

    def test_nested_levels_are_whole_objects(self):
        child = make_level()
        parent = make_level(segments=["<div>", child, "</div>"])
        assert parent.segments[1] is child

    def test_equality_by_value(self):
        assert make_level() == make_level()
        assert make_level() != make_level(root_span=(1, 6))

    def test_slots_reject_undeclared_attributes(self):
        level = make_level()
        with pytest.raises(AttributeError):
            level.markup = "nope"  # pyright: ignore[reportAttributeAccessIssue]

    def test_is_a_slotted_dataclass(self):
        fields = {f.name for f in dataclasses.fields(RenderedLevel)}
        assert fields == {"segments", "root_span", "descriptor"}
        assert not hasattr(make_level(), "__dict__")


def test_segments_module_is_import_pure():
    tree = ast.parse(inspect.getsource(pyjinhx2.segments))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "segments.py must not use relative imports"
            names = [node.module or ""]
        else:
            continue
        internal = [n for n in names if n.startswith("pyjinhx")]
        assert not internal, f"segments.py must not import internal modules: {internal}"
