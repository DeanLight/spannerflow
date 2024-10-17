import networkx as nx
import pytest

from spannerflow.graph_utils import change_node_key, find_output, find_sources


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
