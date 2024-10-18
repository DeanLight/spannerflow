import networkx as nx
import pytest

from spannerflow.graph_utils import (
    change_node_key,
    find_output,
    find_sources,
    get_common_cols,
    get_minus_cols,
    get_node_schema,
)


def test_find_sources():
    # Test for multiple sources
    graph = nx.DiGraph()
    graph.add_edges_from([(1, 2), (2, 3), (4, 3)])
    assert find_sources(graph) == [1, 4]

    # Test for no sources
    graph.add_edges_from([(1, 4), (4, 1)])
    assert find_sources(graph) == []


def test_find_output():
    # Test for single outputs
    graph = nx.DiGraph()
    graph.add_edges_from([(1, 2), (2, 3)])
    assert find_output(graph) == 3

    # Test for multiple outputs
    graph.add_edge(2, 4)
    with pytest.raises(Exception):
        find_output(graph)

    # Test for no outputs
    graph.remove_edge(2, 4)
    graph.remove_node(4)
    graph.add_edge(3, 1)
    with pytest.raises(Exception):
        find_output(graph)


def test_change_node_key():
    graph = nx.DiGraph()
    graph.add_edges_from([(1, 2), (2, 3)])
    graph.nodes[1]["attr"] = "value"
    change_node_key(graph, 1, 10)
    assert 1 not in graph.nodes
    assert 10 in graph.nodes
    assert graph.nodes[10]["attr"] == "value"


def test_get_node_schema():
    graph = nx.DiGraph()
    graph.add_node(
        1, schema=["col1", "col2"], schema_types=["DATA_TYPE_INT", "DATA_TYPE_STRING"]
    )
    assert get_node_schema(graph, 1) == "(col1, col2)"
    with pytest.raises(KeyError):
        get_node_schema(graph, 2)
    graph.add_node(2, schema=["col1"], schema_types=["DATA_TYPE_INT"])
    assert get_node_schema(graph, 2) == "col1"
    # empty schema case -
    # TODO: is it valid? Should we raise an exception?
    graph.add_node(3, schema=[], schema_types=[])
    assert get_node_schema(graph, 3) == "()"


def test_get_common_cols():
    graph = nx.DiGraph()
    graph.add_node(1, schema=["col1", "col2"])
    graph.add_node(2, schema=["col2", "col3"])

    assert get_common_cols(graph, 1, 2) == ["col2"]

    graph.add_node(3, schema=["col1", "col2", "col3"])
    assert set(get_common_cols(graph, 1, 3)) == {"col1", "col2"}
    assert set(get_common_cols(graph, 2, 3)) == {"col2", "col3"}

    graph.add_node(4, schema=["col5"])
    assert get_common_cols(graph, 1, 4) == []
    assert get_common_cols(graph, 2, 4) == []
    assert get_common_cols(graph, 3, 4) == []


def test_get_minus_cols():
    graph = nx.DiGraph()
    graph.add_node(1, schema=["col1", "col2"])
    graph.add_node(2, schema=["col2", "col3"])

    assert get_minus_cols(graph, 1, ["col1"]) == ["col2"]
    assert get_minus_cols(graph, 1, ["col1", "col2"]) == []
    assert get_minus_cols(graph, 1, ["col2"]) == ["col1"]
    assert set(get_minus_cols(graph, 1, ["col3"])) == {"col1", "col2"}
    assert set(get_minus_cols(graph, 2, ["col1"])) == {"col2", "col3"}
    assert get_minus_cols(graph, 2, ["col1", "col2"]) == ["col3"]
    assert get_minus_cols(graph, 2, ["col2"]) == ["col3"]
    assert get_minus_cols(graph, 2, ["col3"]) == ["col2"]
