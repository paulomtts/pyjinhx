from typing import ClassVar

from pyjinhx import ReactiveComponent
from pyjinhx.utils import read_client_runtime


class SkeletonCounter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}
    loading: ClassVar[str] = "skeleton"

    @classmethod
    def load(cls) -> "SkeletonCounter":
        return cls(id="skeleton-counter", remaining=0)


class SpinnerButton(ReactiveComponent):
    completed: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}
    loading: ClassVar[str] = "spinner"

    @classmethod
    def load(cls) -> "SpinnerButton":
        return cls(id="spin-btn", completed=0)


class PlainCounter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "PlainCounter":
        return cls(id="plain-counter", remaining=0)


def test_skeleton_component_stamps_loading_and_reacts():
    html = str(SkeletonCounter(id="c1", remaining=2)._render(source="<span>{{ remaining }}</span>"))
    assert 'data-pjx-loading="skeleton"' in html
    assert 'data-pjx-reacts="todos"' in html


def test_spinner_component_stamps_loading_spinner():
    html = str(SpinnerButton(id="b1", completed=1)._render(source="<button>{{ completed }}</button>"))
    assert 'data-pjx-loading="spinner"' in html
    assert 'data-pjx-reacts="todos"' in html


def test_default_component_stamps_reacts_but_no_loading():
    html = str(PlainCounter(id="c2", remaining=2)._render(source="<span>{{ remaining }}</span>"))
    assert 'data-pjx-reacts="todos"' in html
    assert "data-pjx-loading" not in html


def test_runtime_has_loading_indicator_logic():
    source = read_client_runtime()
    assert "htmx:beforeRequest" in source
    assert "data-pjx-loading" in source
    assert "pjx-loading--skeleton" in source
    assert "pjx-loading--spinner" in source
    assert "pjx-spin" in source
    assert "data-pjx-reacts" in source
