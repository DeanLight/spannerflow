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


def test_get_input_schema_types(rust_dataflow):
    with patch.object(rust_dataflow._engine, "get_collections") as mock_get_collections:
        mock_get_collections.return_value = {"X": ["DATA_TYPE_INT", "DATA_TYPE_STRING"]}
        assert rust_dataflow.get_input_schema_types("X") == [
            "DATA_TYPE_INT",
            "DATA_TYPE_STRING",
        ]


def test_get_input_schema(rust_dataflow):
    with patch.object(rust_dataflow._engine, "get_collections") as mock_get_collections:
        mock_get_collections.return_value = {"X": ["DATA_TYPE_INT", "DATA_TYPE_STRING"]}
        assert rust_dataflow.get_input_schema("X") == ["i32", "String"]


def test_get_col_schema(rust_dataflow):
    assert rust_dataflow.get_col_schema(["col1", "col2"]) == "(col1, col2)"
    assert rust_dataflow.get_col_schema(["col1"]) == "col1"
    assert rust_dataflow.get_col_schema([]) == "0"


def test_get_output_data(rust_dataflow):
    graph = nx.DiGraph()
    graph.add_node(1, schema=["col1"], schema_types=["DATA_TYPE_INT"])
    graph.add_node(2, schema=["col1"], schema_types=["DATA_TYPE_INT"])
    graph.add_edge(1, 2)
    output_node, output_vars = rust_dataflow.get_output_data(graph)
    assert output_node == 2
    assert output_vars == 1


def test_get_node_str(rust_dataflow):
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
