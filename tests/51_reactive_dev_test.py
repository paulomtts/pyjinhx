import logging
from typing import ClassVar

import pytest

from pyjinhx import ReactiveComponent, Registry, mutates
from pyjinhx.cache import LoadCache
from pyjinhx.dev import (
    dependency_graph,
    disable_reactive_dev,
    enable_reactive_dev,
    format_dependency_graph,
)


@mutates("orphan")
def _orphan_mutation() -> None:
    pass


class DevCounter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "DevCounter":
        return cls(id="counter", remaining=0)


def setup_function():
    disable_reactive_dev()
    LoadCache.clear()


def teardown_function():
    disable_reactive_dev()


def test_warn_mutations_without_render(caplog):
    enable_reactive_dev()
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        with Registry.request_scope():
            _orphan_mutation()
    assert "no reactive render" in caplog.text.lower()


def test_strict_mutations_without_render_raises():
    enable_reactive_dev(strict=True)
    with pytest.raises(RuntimeError, match="no reactive render"):
        with Registry.request_scope():
            _orphan_mutation()


def test_warn_render_without_client(caplog):
    from pyjinhx.dev import warn_reactive_render_without_client
    from pyjinhx.mutations import MutationTracker

    enable_reactive_dev()
    MutationTracker.clear()
    MutationTracker.record({"todos"})
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        warn_reactive_render_without_client(backend=None)
    assert "clientbackend" in caplog.text.lower()


def test_dependency_graph_includes_reactive_components():
    graph = dependency_graph()
    assert "todos" in graph
    assert "DevCounter" in graph["todos"]


def test_format_dependency_graph_mermaid():
    output = format_dependency_graph(as_mermaid=True)
    assert "flowchart LR" in output
    assert "DevCounter" in output
