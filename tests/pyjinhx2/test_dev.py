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


def test_format_dependency_graph_plain_text():
    text = dev.format_dependency_graph()
    assert text.startswith("Reactive dependency graph:")
    assert "'todo' -> TodoBadge, TodoList" in text


def test_format_dependency_graph_as_mermaid():
    text = dev.format_dependency_graph(as_mermaid=True)
    lines = text.splitlines()
    assert lines[0] == "flowchart LR"
    assert '  key_todo["todo"]' in lines
    assert "  key_todo --> TodoList" in lines
    assert "  key_todo --> TodoBadge" in lines


def test_format_dependency_graph_empty(monkeypatch):
    monkeypatch.setattr(dev, "dependency_graph", dict)
    assert dev.format_dependency_graph() == "(no reactive components registered)"
    assert dev.format_dependency_graph(as_mermaid=True) == "flowchart LR"


@pytest.fixture(autouse=True)
def _reset_dev_mode():
    """Leave dev mode off after every test, whatever the test turned on."""
    yield
    dev.disable_reactive_dev()


def test_unconsumed_mutation_warns_when_not_strict(caplog):
    dev.enable_reactive_dev()
    with request_scope(), caplog.at_level(logging.WARNING, logger="pyjinhx"):
        add_dirtied({"ghost"})
        dev.warn_unconsumed_mutations()
    assert "ghost" in caplog.text


def test_unconsumed_mutation_raises_when_strict():
    dev.enable_reactive_dev(strict=True)
    with request_scope():
        add_dirtied({"ghost"})
        with pytest.raises(RuntimeError, match="ghost"):
            dev.warn_unconsumed_mutations()


def test_consumed_mutation_is_not_reported():
    dev.enable_reactive_dev(strict=True)
    with request_scope():
        cache_put(TodoList, None, ["a todo"], react_keys=("todo",))
        add_dirtied({"todo"})
        dev.warn_unconsumed_mutations()


def test_no_dirtied_keys_is_a_no_op():
    dev.enable_reactive_dev(strict=True)
    with request_scope():
        dev.warn_unconsumed_mutations()


def test_disabled_dev_mode_suppresses_the_check():
    dev.disable_reactive_dev()
    with request_scope():
        add_dirtied({"ghost"})
        dev.warn_unconsumed_mutations()


def test_dev_mode_toggles_back_on_after_disable():
    dev.enable_reactive_dev(strict=True)
    dev.disable_reactive_dev()
    dev.enable_reactive_dev(strict=True)
    with request_scope():
        add_dirtied({"ghost"})
        with pytest.raises(RuntimeError):
            dev.warn_unconsumed_mutations()
