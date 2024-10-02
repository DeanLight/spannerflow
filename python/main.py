import asyncio
import inspect
from dataclasses import dataclass
from typing import AsyncGenerator, Generator

import grpc

from dataflow.v1 import dataflow_pb2, dataflow_pb2_grpc

_IE_FUNCTIONS = {}


@dataclass
class Config:
    LISTEN_PORT: int = 50052
    LISTEN_IP: str = "localhost"
    LISTEN_ADDRESS: str = f"{LISTEN_IP}:{LISTEN_PORT}"
    DATAFLOW_PORT: int = 50051
    DATAFLOW_IP: str = "localhost"
    DATAFLOW_ADDRESS: str = f"{DATAFLOW_IP}:{DATAFLOW_PORT}"


def register_function(func):
    signature = inspect.signature(func)
    parameters = signature.parameters
    # Check for mandatory arguments
    mandatory_count = sum(
        1
        for p in parameters.values()
        if p.default == inspect.Parameter.empty
        and p.kind
        not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
    )

    if mandatory_count > 1 or len(parameters) == 0:
        raise ValueError(
            f"{func.__name__} must have at least one argument. and at most one not default argument"
        )

    # Register the function in the global dictionary
    _IE_FUNCTIONS[func.__name__] = func
    return func


@register_function
async def async_greet(rows: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    async for row in rows:
        yield f"Hello, World! {row}"


@register_function
def sync_greet(rows: Generator[str, None, None]) -> Generator[str, None, None]:
    for row in rows:
        yield f"Hello, World! {row}"


class IEFunctionService(dataflow_pb2_grpc.IEFunctionServiceServicer):
    async def RunIEFunction(
        self, request: dataflow_pb2.RunIEFunctionRequest, context  # type: ignore
    ) -> AsyncGenerator[dataflow_pb2.RunIEFunctionResponse, None]:  # type: ignore
        # Here you would implement your logic for running the IE function
        collection_name = request.collection_name
        function_name = request.function_name
        func = _IE_FUNCTIONS.get(function_name)
        if func is None:
            context.set_details("IE Function not found.")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return  # Return early after setting the error
        if inspect.isasyncgenfunction(func):
            async for row in func(get_collection_async(collection_name)):
                yield dataflow_pb2.RunIEFunctionResponse(row=row)  # type: ignore

        else:
            for row in func(get_collection_sync(collection_name)):
                yield dataflow_pb2.RunIEFunctionResponse(row=row)  # type: ignore


def get_collection_sync(collection_name):
    with grpc.insecure_channel(Config.DATAFLOW_ADDRESS) as channel:
        # Create a stub (client)
        stub = dataflow_pb2_grpc.DataflowServiceStub(channel)

        # Prepare the request
        request = dataflow_pb2.GetCollectionRequest(collection_name=collection_name)  # type: ignore

        # Call the GetCollection method and receive a stream of responses
        response_iterator = stub.GetCollection(request)

        for response in response_iterator:
            yield response.row


async def get_collection_async(collection_name):
    async with grpc.aio.insecure_channel(Config.DATAFLOW_ADDRESS) as channel:
        # Create a stub (client)
        stub = dataflow_pb2_grpc.DataflowServiceStub(channel)

        # Prepare the request
        request = dataflow_pb2.GetCollectionRequest(collection_name=collection_name)  # type: ignore

        # Call the GetCollection method and receive a stream of responses
        response_iterator = stub.GetCollection(request)

        async for response in response_iterator:
            yield response.row


async def serve() -> None:
    server = grpc.aio.server()
    dataflow_pb2_grpc.add_IEFunctionServiceServicer_to_server(
        IEFunctionService(), server
    )

    server.add_insecure_port(Config.LISTEN_ADDRESS)
    await server.start()
    await server.wait_for_termination()  # Keep the server running


if __name__ == "__main__":
    asyncio.run(serve())
