"""Unit tests for pyjinhx2.dev: the dependency graph and the unconsumed-mutation check."""

import logging

import pytest

from pyjinhx2 import dev
from pyjinhx2.component import BaseComponent
from pyjinhx2.reactive.cache import cache_put
from pyjinhx2.reactive.component import ReactiveComponent
from pyjinhx2.session import add_dirtied, request_scope


class PlainWidget(BaseComponent):
    """A non-reactive component; must never appear in the dependency graph."""

    template: str = "<div>plain</div>"


class TodoList(ReactiveComponent, react=("todo",)):
    template: str = "<div>todos</div>"


class TodoBadge(ReactiveComponent, react=("todo", "user")):
    template: str = "<div>badge</div>"


def test_dependency_graph_includes_reactive_components():
    graph = dev.dependency_graph()
    assert "TodoList" in graph["todo"]
    assert "TodoBadge" in graph["todo"]
    assert graph["user"] == ["TodoBadge"]


def test_dependency_graph_excludes_non_reactive_components():
    graph = dev.dependency_graph()
    assert all("PlainWidget" not in names for names in graph.values())
