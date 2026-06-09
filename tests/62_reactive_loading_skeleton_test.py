from typing import ClassVar

from pyjinhx import ReactiveComponent


class ShimmerCounter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}
    loading_skeleton: ClassVar[bool] = True

    @classmethod
    def load(cls) -> "ShimmerCounter":
        return cls(id="shimmer-counter", remaining=0)


class PlainCounter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "PlainCounter":
        return cls(id="plain-counter", remaining=0)


def test_opted_in_component_stamps_skeleton_and_reacts():
    html = str(ShimmerCounter(id="c1", remaining=2)._render(source="<span>{{ remaining }}</span>"))
    assert 'data-pjx-skeleton="true"' in html
    assert 'data-pjx-reacts="todos"' in html


def test_default_component_stamps_reacts_but_not_skeleton():
    html = str(PlainCounter(id="c2", remaining=2)._render(source="<span>{{ remaining }}</span>"))
    assert 'data-pjx-reacts="todos"' in html
    assert "data-pjx-skeleton" not in html
