from pathlib import Path
from typing import Any, Generator

import grpc
import networkx as nx
from google.protobuf import empty_pb2
from google.protobuf.json_format import MessageToDict
from singleton_decorator import singleton

from spannerflow.config import Config
from spannerflow.dataflow.v1 import dataflow_pb2, dataflow_pb2_grpc
from spannerflow.graph_utils import find_output


@singleton
class Engine:
    def __init__(self, config: Config = Config(), allow_reuse_server: bool = False):
        from spannerflow.rust_dataflow import RustDataflow

        self._config = config
        self._rust_dataflow = RustDataflow(config=config, engine=self)
        self._is_open = False

    def __enter__(self):
        self._rust_dataflow.__enter__()
        self._is_open = True
        return self

    def open(self):
        if self._is_open:
            return

        self.__enter__()

    def close(self):
        if not self._is_open:
            return
        self.__exit__(None, None, None)

    def __exit__(self, exc_type, exc_value, traceback):
        self._rust_dataflow.__exit__(exc_type, exc_value, traceback)
        self._is_open = False

    def save_to_csv(self, collection_name: str, file_path: Path) -> None:
        with grpc.insecure_channel(self._config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.SaveToCSVRequest(  # type: ignore
                collection_name=collection_name, file_path=str(file_path)
            )
            stub.SaveToCSV(request)

    def load_from_csv(self, collection_name: str, file_path: Path) -> None:
        with grpc.insecure_channel(self._config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.LoadFromCSVRequest(  # type: ignore
                collection_name=collection_name, file_path=str(file_path)
            )
            stub.LoadFromCSV(request)

    def add_row(self, collection_name: str, row: list[Any]) -> None:
        with grpc.insecure_channel(self._config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.AddRowRequest(  # type: ignore
                collection_name=collection_name,
                row=self._serialize_row(self.get_collections()[collection_name], row),
            )
            stub.AddRow(request)

    def delete_row(self, collection_name: str, row: list[Any]) -> None:
        with grpc.insecure_channel(self._config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.DeleteRowRequest(  # type: ignore
                collection_name=collection_name,
                row=self._serialize_row(self.get_collections()[collection_name], row),
            )
            stub.DeleteRow(request)

    def add_collection(self, collection_name: str, schema: list[int]) -> None:
        with grpc.insecure_channel(self._config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.AddCollectionRequest(  # type: ignore
                collection_name=collection_name, schema=schema
            )
            stub.AddCollection(request)

    def delete_collection(self, collection_name: str) -> None:
        with grpc.insecure_channel(self._config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.DeleteCollectionRequest(  # type: ignore
                collection_name=collection_name
            )
            stub.DeleteCollection(request)

    def get_collections(self) -> dict[str, list[str]]:
        with grpc.insecure_channel(self._config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = empty_pb2.Empty()
            response = stub.GetCollections(request)
            return {
                d["name"]: d["schema"] for d in MessageToDict(response)["collections"]
            }

    def get_collection(self, collection_name) -> Generator[list[str], None, None]:
        schema = self.get_collections()[collection_name]
        with grpc.insecure_channel(self._config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.GetCollectionRequest(collection_name=collection_name)  # type: ignore
            response_iterator = stub.GetCollection(request)

            for response in response_iterator:
                yield self._deserialize_row(schema, response.row)

    @staticmethod
    def _deserialize_row(schema: list[str], row: list[str]) -> list[Any]:
        new_row: list[Any] = list()
        for col_type, value in zip(schema, row):
            match dataflow_pb2.DataType.Value(col_type):  # type: ignore
                case dataflow_pb2.DataType.DATA_TYPE_STRING:  # type: ignore
                    new_row.append(value)  # alread a string
                case dataflow_pb2.DataType.DATA_TYPE_INT:  # type: ignore
                    new_row.append(int(value))
                case dataflow_pb2.DataType.DATA_TYPE_FLOAT:  # type: ignore
                    new_row.append(float(value))
                case dataflow_pb2.DataType.DATA_TYPE_BOOL:  # type: ignore
                    new_row.append(value.lower() == "true")
                case _:
                    raise ValueError(f"Unknown data type: {col_type}")
        return new_row

    @staticmethod
    def _serialize_row(schema: list[str], row: list[Any]) -> list[str]:
        new_row = list()
        for col_type, value in zip(schema, row):
            match dataflow_pb2.DataType.Value(col_type):  # type: ignore
                case dataflow_pb2.DataType.DATA_TYPE_STRING:  # type: ignore
                    if not isinstance(value, str):
                        raise ValueError(f"Expected str, got {type(value)}")
                    new_row.append(value)
                case dataflow_pb2.DataType.DATA_TYPE_INT:  # type: ignore
                    if not isinstance(value, int):
                        raise ValueError(f"Expected int, got {type(value)}")
                    new_row.append(str(value))
                case dataflow_pb2.DataType.DATA_TYPE_FLOAT:  # type: ignore
                    if not isinstance(value, (float, int)) or value == float("nan"):
                        raise ValueError(
                            f"Expected float/int, got {value} ({type(value)})"
                        )
                    new_row.append(str(value))
                case dataflow_pb2.DataType.DATA_TYPE_BOOL:  # type: ignore
                    if not isinstance(value, bool):
                        raise ValueError(f"Expected bool, got {type(value)}")
                    new_row.append(str(value).lower())
                case _:
                    raise ValueError(f"Unknown data type: {col_type}")
        return new_row

    def run_dataflow(
        self,
        reversed_graph: nx.DiGraph,
    ) -> Generator[list[str], None, None]:
        so_path, fn_name = self._rust_dataflow.build_so(reversed_graph)

        with grpc.insecure_channel(self._config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.RunDataflowRequest(  # type: ignore
                so_path=str(so_path),
                fn_name=fn_name,
            )
            response_iterator = stub.RunDataflow(request)
            schema_types = reversed_graph.nodes[find_output(reversed_graph)][
                "schema_types"
            ]
            for response in response_iterator:
                yield self._deserialize_row(
                    schema_types, [str(item) for item in response.row]
                )
