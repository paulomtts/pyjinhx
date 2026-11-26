"""Level and child-ref builders for the segment tests."""

from pyjinhx.rendering.segments import ChildRef, RenderedLevel


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
