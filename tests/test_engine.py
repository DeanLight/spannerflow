from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spannerflow.config import Config
from spannerflow.dataflow.v1 import dataflow_pb2
from spannerflow.engine import Engine


@pytest.fixture
def engine():
    config = Config()
    Engine._instance = None
    with patch("spannerflow.engine.Engine.__new__", return_value=None):
        instance = Engine(config=config)
        instance._config = config
        instance._is_open = False
        instance._rust_dataflow = MagicMock()
        return instance


def test_engine_save_to_csv(engine):
    with patch("grpc.insecure_channel"), patch(
        "spannerflow.dataflow.v1.dataflow_pb2_grpc.DataflowServiceStub"
    ) as mock_stub:
        mock_stub.return_value.SaveToCSV = MagicMock()
        engine.save_to_csv("test_collection", Path("/tmp/test.csv"))
        mock_stub.return_value.SaveToCSV.assert_called_once()


def test_engine_load_from_csv(engine):
    with patch("grpc.insecure_channel"), patch(
        "spannerflow.dataflow.v1.dataflow_pb2_grpc.DataflowServiceStub"
    ) as mock_stub:
        mock_stub.return_value.LoadFromCSV = MagicMock()
        engine.load_from_csv("test_collection", Path("/tmp/test.csv"))
        mock_stub.return_value.LoadFromCSV.assert_called_once()


def test_engine_add_row(engine):
    with patch("grpc.insecure_channel"), patch(
        "spannerflow.dataflow.v1.dataflow_pb2_grpc.DataflowServiceStub"
    ) as mock_stub:
        mock_stub.return_value.AddRow = MagicMock()
        mock_stub.return_value.GetCollections = MagicMock(
            return_value=dataflow_pb2.GetCollectionsResponse(
                collections=[
                    dataflow_pb2.Collection(
                        name="test_collection",
                        schema=[
                            dataflow_pb2.DATA_TYPE_INT,
                            dataflow_pb2.DATA_TYPE_STRING,
                        ],
                    )
                ]
            )
        )
        engine.add_row("test_collection", [2, "col1"])
        mock_stub.return_value.AddRow.assert_called_once()


def test_engine_delete_row(engine):
    with patch("grpc.insecure_channel"), patch(
        "spannerflow.dataflow.v1.dataflow_pb2_grpc.DataflowServiceStub"
    ) as mock_stub:
        mock_stub.return_value.DeleteRow = MagicMock()
        mock_stub.return_value.GetCollections = MagicMock(
            return_value=dataflow_pb2.GetCollectionsResponse(
                collections=[
                    dataflow_pb2.Collection(
                        name="test_collection",
                        schema=[
                            dataflow_pb2.DATA_TYPE_INT,
                            dataflow_pb2.DATA_TYPE_STRING,
                        ],
                    )
                ]
            )
        )
        engine.delete_row("test_collection", [2, "col1"])
        mock_stub.return_value.DeleteRow.assert_called_once()


def test_engine_add_collection(engine):
    with patch("grpc.insecure_channel"), patch(
        "spannerflow.dataflow.v1.dataflow_pb2_grpc.DataflowServiceStub"
    ) as mock_stub:
        mock_stub.return_value.AddCollection = MagicMock()
        engine.add_collection("test_collection", ["DATA_TYPE_INT", "DATA_TYPE_STRING"])
        mock_stub.return_value.AddCollection.assert_called_once()


def test_engine_delete_collection(engine):
    with patch("grpc.insecure_channel"), patch(
        "spannerflow.dataflow.v1.dataflow_pb2_grpc.DataflowServiceStub"
    ) as mock_stub:
        mock_stub.return_value.DeleteCollection = MagicMock()
        engine.delete_collection("test_collection")
        mock_stub.return_value.DeleteCollection.assert_called_once()


def test_engine_get_collections(engine):
    with patch("grpc.insecure_channel"), patch(
        "spannerflow.dataflow.v1.dataflow_pb2_grpc.DataflowServiceStub"
    ) as mock_stub:
        mock_stub.return_value.GetCollections = MagicMock(
            return_value=dataflow_pb2.GetCollectionsResponse(
                collections=[
                    dataflow_pb2.Collection(
                        name="test_collection",
                        schema=[
                            dataflow_pb2.DATA_TYPE_INT,
                            dataflow_pb2.DATA_TYPE_STRING,
                        ],
                    )
                ]
            )
        )
        collections = engine.get_collections()
        mock_stub.return_value.GetCollections.assert_called_once()
        assert collections == {"test_collection": ["DATA_TYPE_INT", "DATA_TYPE_STRING"]}
        mock_stub.return_value.GetCollections = MagicMock(
            return_value=dataflow_pb2.GetCollectionsResponse()
        )
        collections = engine.get_collections()
        mock_stub.return_value.GetCollections.assert_called_once()
        assert collections == {}


def test_engine__serialize_row(engine):
    row = [2, "col1", 1.0, False]
    schema = ["DATA_TYPE_INT", "DATA_TYPE_STRING", "DATA_TYPE_FLOAT", "DATA_TYPE_BOOL"]
    serialized = engine._serialize_row(schema, row)
    assert serialized == ["2", "col1", "1.0", "false"]

    with pytest.raises(ValueError):
        engine._serialize_row(["DATA_TYPE_INT"], ["col1"])
    with pytest.raises(ValueError):
        engine._serialize_row(["DATA_TYPE_INT"], [1.1])
    with pytest.raises(ValueError):
        engine._serialize_row(["DATA_TYPE_FLOAT"], [float("nan")])
    with pytest.raises(ValueError):
        engine._serialize_row(["DATA_TYPE_STRING"], [float("nan")])
    with pytest.raises(ValueError):
        engine._serialize_row(["DATA_TYPE_UNSPECIFIED"], [float("nan")])
    with pytest.raises(ValueError):
        engine._serialize_row(["DATA_TYPE_BOOL"], [float("nan")])
    with pytest.raises(ValueError):
        engine._serialize_row(["DATA_TYPE_BOOL"], [None])


def test_engine__deserialize_row(engine):
    row = ["2", "col1", "1.0", "false"]
    schema = ["DATA_TYPE_INT", "DATA_TYPE_STRING", "DATA_TYPE_FLOAT", "DATA_TYPE_BOOL"]
    deserialized = engine._deserialize_row(schema, row)
    assert deserialized == [2, "col1", 1.0, False]

    with pytest.raises(ValueError):
        engine._deserialize_row(["DATA_TYPE_INT"], ["col1"])

    with pytest.raises(ValueError):
        engine._deserialize_row(["DATA_TYPE_FLOAT"], ["nan"])

    with pytest.raises(ValueError):
        engine._deserialize_row(["DATA_TYPE_UNSPECIFIED"], ["aaa"])

    with pytest.raises(ValueError):
        engine._deserialize_row(["DATA_TYPE_BOOL"], ["aaa"])

    with pytest.raises(ValueError):
        engine._deserialize_row(["DATA_TYPE_BOOL"], ["NULL"])

    with pytest.raises(ValueError):
        engine._deserialize_row(["DATA_TYPE_BOOL"], ["None"])

    with pytest.raises(ValueError):
        engine._deserialize_row(["DATA_TYPE_BOOL"], ["False"])

    with pytest.raises(ValueError):
        engine._deserialize_row(["DATA_TYPE_BOOL"], ["True"])
