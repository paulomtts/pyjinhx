from pyjinhx.dev import dependency_graph, format_dependency_graph


def test_dependency_graph_values_are_sorted():
    graph = dependency_graph()
    for components in graph.values():
        assert components == sorted(components)


def test_format_dependency_graph_text():
    output = format_dependency_graph()
    assert "Reactive dependency graph" in output
