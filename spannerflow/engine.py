from pathlib import Path
from typing import Generator

import grpc
from google.protobuf import empty_pb2
from google.protobuf.json_format import MessageToDict

from spannerflow.config import Config
from spannerflow.dataflow.v1 import dataflow_pb2, dataflow_pb2_grpc


class Engine:
    def __init__(self, config: Config):
        self.config = config

    def add_row(self, collection_name: str, row: list[str]) -> None:
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.AddRowRequest(  # type: ignore
                collection_name=collection_name, row=row
            )
            stub.AddRow(request)

    def delete_row(self, collection_name: str, row: list[str]) -> None:
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.DeleteRowRequest(  # type: ignore
                collection_name=collection_name, row=row
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
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.GetCollectionRequest(collection_name=collection_name)  # type: ignore
            response_iterator = stub.GetCollection(request)

            for response in response_iterator:
                yield response.row

    def run_dataflow(
        self,
        so_path: Path,
        fn_name: str,
        input_collection_name: str,
        output_collection_name: str | None = None,
    ) -> Generator[list[str], None, None]:
        with grpc.insecure_channel(self.config.DATAFLOW_ADDRESS) as channel:
            stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
            request = dataflow_pb2.RunDataflowRequest(  # type: ignore
                so_path=str(so_path),
                fn_name=fn_name,
                input_collection_name=input_collection_name,
                output_collection_name=output_collection_name,
            )
            response_iterator = stub.RunDataflow(request)

            for response in response_iterator:
                yield response.row
