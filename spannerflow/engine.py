from pathlib import Path
from typing import Any, Generator

import grpc
import networkx as nx
from google.protobuf import empty_pb2
from google.protobuf.json_format import MessageToDict

from spannerflow.config import Config
from spannerflow.dataflow.v1 import dataflow_pb2, dataflow_pb2_grpc
from spannerflow.graph_utils import find_output


class Engine:
    def __init__(self, config: Config):
        self.config = config

    def save_to_csv(self, collection_name: str, file_path: Path) -> None:
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.SaveToCSVRequest(  # type: ignore
                collection_name=collection_name, file_path=str(file_path)
            )
            stub.SaveToCSV(request)

    def load_from_csv(self, collection_name: str, file_path: Path) -> None:
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.LoadFromCSVRequest(  # type: ignore
                collection_name=collection_name, file_path=str(file_path)
            )
            stub.LoadFromCSV(request)

    def add_row(self, collection_name: str, row: list[Any]) -> None:
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.AddRowRequest(  # type: ignore
                collection_name=collection_name,
                row=[
                    str(item).lower() if isinstance(item, bool) else str(item)
                    for item in row
                ],
            )
            stub.AddRow(request)

    def delete_row(self, collection_name: str, row: list[Any]) -> None:
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.DeleteRowRequest(  # type: ignore
                collection_name=collection_name,
                row=[
                    str(item).lower() if isinstance(item, bool) else str(item)
                    for item in row
                ],
            )
            stub.DeleteRow(request)

    def add_collection(self, collection_name: str, schema: list[int]) -> None:
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.AddCollectionRequest(  # type: ignore
                collection_name=collection_name, schema=schema
            )
            stub.AddCollection(request)

    def delete_collection(self, collection_name: str) -> None:
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.DeleteCollectionRequest(  # type: ignore
                collection_name=collection_name
            )
            stub.DeleteCollection(request)

    def get_collections(self) -> dict[str, list[str]]:
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = empty_pb2.Empty()
            response = stub.GetCollections(request)
            return {
                d["name"]: d["schema"] for d in MessageToDict(response)["collections"]
            }

    def get_collection(self, collection_name) -> Generator[list[str], None, None]:
        schema = self.get_collections()[collection_name]
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.GetCollectionRequest(collection_name=collection_name)  # type: ignore
            response_iterator = stub.GetCollection(request)

            for response in response_iterator:
                yield self._cast_row(schema, response.row)

    @staticmethod
    def _cast_row(schema: list[str], row: list[Any]) -> list[str]:
        new_row = list()
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

    def run_dataflow(
        self,
        reversed_graph: nx.DiGraph,
    ) -> Generator[list[str], None, None]:
        from spannerflow.rust import build_so

        so_path, fn_name = build_so(reversed_graph)

        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
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
                yield self._cast_row(schema_types, [str(item) for item in response.row])
