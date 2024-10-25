from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from spannerflow.config import Config
from spannerflow.engine import Engine
from spannerflow.rust_dataflow import RustDataflow


@pytest.fixture
def rust_dataflow():
    Engine._instance = None
    config = Config()
    with patch(
        "spannerflow.engine.Engine.__init__", return_value=MagicMock(spec=Engine)
    ) as mock_engine:
        instance = RustDataflow(config=config, engine=mock_engine)
        return instance


def test_dataflow_get_input_schema_types(rust_dataflow):
    with patch.object(rust_dataflow._engine, "get_collections") as mock_get_collections:
        mock_get_collections.return_value = {"X": ["DATA_TYPE_INT", "DATA_TYPE_STRING"]}
        assert rust_dataflow.get_input_schema_types("X") == [
            "DATA_TYPE_INT",
            "DATA_TYPE_STRING",
        ]


def test_dataflow_get_input_schema(rust_dataflow):
    with patch.object(rust_dataflow._engine, "get_collections") as mock_get_collections:
        mock_get_collections.return_value = {"X": ["DATA_TYPE_INT", "DATA_TYPE_STRING"]}
        assert rust_dataflow.get_input_schema("X") == ["i32", "String"]


def test_dataflow_get_col_schema(rust_dataflow):
    assert rust_dataflow.get_col_schema(["col1", "col2"]) == "(col1, col2)"
    assert rust_dataflow.get_col_schema(["col1"]) == "col1"
    assert rust_dataflow.get_col_schema([]) == "0"


def test_dataflow_get_node_str(rust_dataflow):
    str_anchor = "ANCHOR"
    assert (
        rust_dataflow.get_node_str(1, anchor=str_anchor, in_iterate=False) == "node_1"
    )
    assert (
        rust_dataflow.get_node_str("X", anchor=str_anchor, in_iterate=False) == "node_X"
    )
    assert (
        rust_dataflow.get_node_str(str_anchor, anchor=str_anchor, in_iterate=True)
        == str_anchor
    )
    assert (
        rust_dataflow.get_node_str(str_anchor, anchor=str_anchor, in_iterate=False)
        == f"node_{str_anchor}"
    )
    int_anchor = 1
    assert rust_dataflow.get_node_str(
        int_anchor, anchor=int_anchor, in_iterate=True
    ) == str(int_anchor)
    assert (
        rust_dataflow.get_node_str(int_anchor, anchor=int_anchor, in_iterate=False)
        == f"node_{int_anchor}"
    )


def test_dataflow_get_sources_data(rust_dataflow):
    with patch.object(rust_dataflow._engine, "get_collections") as mock_get_collections:
        mock_get_collections.return_value = {
            "X": ["DATA_TYPE_INT", "DATA_TYPE_STRING"],
        }
        graph = nx.DiGraph()
        graph.add_nodes_from(
            [
                ("X", {"op": "get_rel"}),
                (
                    "Y",
                    {
                        "op": "get_const",
                        "schema": ["col1"],
                        "schema_types": ["DATA_TYPE_FLOAT"],
                        "const_dict": {"col1": 1.0},
                    },
                ),
            ]
        )
        assert rust_dataflow.get_sources_data(graph) == {
            "X": {"name": "X", "op": "get_rel", "schema": ["i32", "String"]},
            "Y": {
                "name": "Y",
                "op": "get_const",
                "schema": ["OrderedFloat<f32>"],
                "consts": ["1.0"],
            },
        }


def test_dataflow_get_from_input_code(rust_dataflow):
    graph = nx.DiGraph()
    graph.add_node(
        1,
        op="get_const",
        schema=["col1"],
        schema_types=["DATA_TYPE_FLOAT"],
        const_dict={"col1": 1.0},
    )
    node = 1
    anchor = None
    in_iterate = False

    assert (
        rust_dataflow.get_from_input_code(graph, node, anchor, in_iterate)
        == "let node_1 = input_1.to_collection(scope);"
    )


def test_dataflow___enter__(rust_dataflow):
    with patch.object(
        rust_dataflow, "_run_rust_server_in_background"
    ) as mock_run_rust_server_in_background:
        rust_dataflow._is_server_running = True
        obj = rust_dataflow.__enter__()
        mock_run_rust_server_in_background.assert_not_called()
        assert obj == rust_dataflow

        rust_dataflow._is_server_running = False
        obj = rust_dataflow.__enter__()
        mock_run_rust_server_in_background.assert_called_once()
        assert obj == rust_dataflow


def test_dataflow___exit__(rust_dataflow):
    with patch.object(rust_dataflow, "_stop_rust_server") as mock_stop_rust_server:
        rust_dataflow._is_server_running = False
        rust_dataflow.__exit__(None, None, None)
        mock_stop_rust_server.assert_not_called()

        rust_dataflow._is_server_running = True
        rust_dataflow.__exit__(None, None, None)
        mock_stop_rust_server.assert_called_once()


def test_validate_node(rust_dataflow):
    graph = nx.DiGraph()
    graph.add_node(
        0,
        op="get_const",
        schema=["col1"],
        const_dict={"col1": 1.0},
    )
    assert rust_dataflow.validate_node(graph, 0) is None
    graph.add_node(
        "X",
        op="get_rel",
        schema=["col2"],
    )
    assert rust_dataflow.validate_node(graph, "X") is None
    graph.add_node(
        2,
        op="rename",
        schema=["X"],
    )
    graph.add_edge(0, 2)
    assert rust_dataflow.validate_node(graph, 2) is None
    graph.add_edge("X", 2)
    with pytest.raises(ValueError):
        rust_dataflow.validate_node(graph, 2)

    graph.remove_node(2)
    graph.add_node(
        3,
        op="product",
        schema=["col1", "col2"],
    )
    graph.add_edge(0, 3)
    with pytest.raises(ValueError):
        rust_dataflow.validate_node(graph, 3)
    graph.add_edge("X", 3)
    assert rust_dataflow.validate_node(graph, 3) is None

    graph.remove_node(3)

    graph.add_node(4, op="ie_map", schema=["col1"], name="not")
    graph.add_edge("X", 4)
    assert rust_dataflow.validate_node(graph, 4) is None
    graph.add_edge(0, 4)
    with pytest.raises(ValueError):
        rust_dataflow.validate_node(graph, 4)
    graph.add_node(
        5,
        op="aaaa",
        schema=["col1"],
    )
    with pytest.raises(ValueError):
        rust_dataflow.validate_node(graph, 5)
