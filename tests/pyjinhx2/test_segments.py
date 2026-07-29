import ast
import dataclasses
import inspect

import pytest

import pyjinhx2.segments
from pyjinhx2.segments import ChildRef, RenderedLevel


def make_level(
    segments: "list[str | ChildRef | RenderedLevel] | None" = None,
    root_span: tuple[int, int] = (0, 5),
    descriptor: object = None,
) -> "RenderedLevel":
    if segments is None:
        segments = ["<div>hi</div>"]
    return RenderedLevel(segments=segments, root_span=root_span, descriptor=descriptor)


def make_child_ref(
    tag: str = "PJXButton",
    attrs: "dict[str, str] | None" = None,
    inner: "str | None" = None,
) -> "ChildRef":
    if attrs is None:
        attrs = {"label": "Go"}
    return ChildRef(tag=tag, attrs=attrs, inner=inner)


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

    def test_child_ref_holds_position_in_segments(self):
        child = make_level()
        ref = make_child_ref()
        parent = make_level(segments=["<div>", ref, child, "</div>"])
        assert parent.segments == ["<div>", ref, child, "</div>"]
        assert parent.segments[1] is ref
        assert parent.segments[2] is child

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


class TestChildRef:
    def test_holds_its_three_fields(self):
        ref = make_child_ref(
            tag="PJXAccordion",
            attrs={"title": "Details"},
            inner="<p>body</p>",
        )
        assert ref.tag == "PJXAccordion"
        assert ref.attrs == {"title": "Details"}
        assert ref.inner == "<p>body</p>"

    def test_inner_is_none_for_self_closing_tags(self):
        ref = make_child_ref(tag="PJXIcon", attrs={"name": "gear"}, inner=None)
        assert ref.inner is None

    def test_equality_by_value(self):
        assert make_child_ref() == make_child_ref()
        assert make_child_ref() != make_child_ref(tag="PJXIcon")
        assert make_child_ref() != make_child_ref(attrs={"label": "Stop"})
        assert make_child_ref() != make_child_ref(inner="<p>body</p>")

    def test_slots_reject_undeclared_attributes(self):
        ref = make_child_ref()
        with pytest.raises(AttributeError):
            ref.resolved = "nope"  # pyright: ignore[reportAttributeAccessIssue]

    def test_is_a_slotted_dataclass(self):
        fields = {f.name for f in dataclasses.fields(ChildRef)}
        assert fields == {"tag", "attrs", "inner"}
        assert not hasattr(make_child_ref(), "__dict__")


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
