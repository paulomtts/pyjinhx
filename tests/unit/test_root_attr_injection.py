from pyjinhx.base import collect_extra_attrs
from pyjinhx.builtins import PJXPopoverTrigger


def test_collect_merges_extra_attrs_field_and_stray_attrs():
    component = PJXPopoverTrigger(
        id="t",
        content="go",
        extra_attrs={"data-explicit": "1"},
        **{"data-stray": "2", "title": "hi"},
    )
    result = collect_extra_attrs(component)
    assert result == {"data-explicit": "1", "data-stray": "2", "title": "hi"}


def test_collect_skips_children_field_and_non_string_extras():
    component = PJXPopoverTrigger(id="t", content="go")
    result = collect_extra_attrs(component)
    # the children field ("content") must not leak into attrs
    assert "content" not in result
    assert result == {}
