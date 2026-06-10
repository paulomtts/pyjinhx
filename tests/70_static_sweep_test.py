from pyjinhx.builtins import (
    Avatar, Badge, Breadcrumb, Card, Divider, EmptyState, Progress, Skeleton, Tooltip,
)

SWEPT = [Avatar, Badge, Breadcrumb, Card, Divider, EmptyState, Progress, Skeleton, Tooltip]


def test_contract_fields_present():
    for cls in SWEPT:
        assert "class_name" in cls.model_fields, cls.__name__
        assert "extra_attrs" in cls.model_fields, cls.__name__


def test_class_name_and_extra_attrs_render():
    html = str(Badge(id="b", label="x", class_name="mine", extra_attrs={"data-k": "v"}).render())
    assert 'class="px-badge px-badge--neutral px-badge--md mine"' in html
    assert 'data-k="v"' in html
    assert 'id="b"' in html  # Badge root gains an id attribute


def test_extra_attrs_values_are_escaped():
    html = str(Badge(id="b", label="x", extra_attrs={"data-k": '"><script>'}).render())
    assert "<script>" not in html


def test_avatar_color():
    html = str(Avatar(id="a", initials="PM", color="#A0C080").render())
    assert "background:#A0C080" in html.replace(" ", "")


def test_breadcrumb_aria_label_prop():
    html = str(Breadcrumb(id="bc", items=[("Home", "/")], aria_label="Caminho").render())
    assert 'aria-label="Caminho"' in html


def test_progress_loading_label_prop():
    html = str(Progress(id="p", loading_label="Carregando").render())
    assert 'aria-label="Carregando"' in html
