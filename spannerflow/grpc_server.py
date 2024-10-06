import asyncio
import inspect
from typing import AsyncGenerator, Generator, Iterable

import grpc

from spannerflow.config import Config
from spannerflow.dataflow.v1 import dataflow_pb2, dataflow_pb2_grpc

_IE_FUNCTIONS = {}


config = Config()


def register_function(func):
    signature = inspect.signature(func)
    parameters = signature.parameters
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

    _IE_FUNCTIONS[func.__name__] = func
    return func


## Example Functions Start ##
@register_function
async def async_greet(
    rows: AsyncGenerator[Iterable[str], None],
) -> AsyncGenerator[list[str], None]:
    async for row in rows:
        yield list(row) + ["Hello, World!"]


@register_function
def sync_greet(
    rows: Generator[Iterable[str], None, None],
) -> Generator[list[str], None, None]:
    for row in rows:
        yield list(row) + ["Hello, World!"]


## Example Functions End ##


class IEFunctionService(dataflow_pb2_grpc.IEFunctionServiceServicer):
    async def RunIEFunction(
        self,
        request: dataflow_pb2.RunIEFunctionRequest,  # type: ignore
        context,
    ) -> AsyncGenerator[dataflow_pb2.RunIEFunctionResponse, None]:  # type: ignore
        collection_name = request.collection_name
        function_name = request.function_name
        func = _IE_FUNCTIONS.get(function_name)
        if func is None:
            context.set_details("IE Function not found.")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return  # Return early after setting the error
        # TODO: Add support for more function structures
        if inspect.isasyncgenfunction(func):
            async for row in func(get_collection_async(collection_name)):
                yield dataflow_pb2.RunIEFunctionResponse(row=row)  # type: ignore

        else:
            for row in func(get_collection_sync(collection_name)):
                yield dataflow_pb2.RunIEFunctionResponse(row=row)  # type: ignore


def get_collection_sync(collection_name):
    with grpc.insecure_channel(config.DATAFLOW_ADDRESS) as channel:
        stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
        request = dataflow_pb2.GetCollectionRequest(collection_name=collection_name)  # type: ignore
        response_iterator = stub.GetCollection(request)

        for response in response_iterator:
            yield response.row


async def get_collection_async(collection_name):
    async with grpc.aio.insecure_channel(config.DATAFLOW_ADDRESS) as channel:
        stub = dataflow_pb2_grpc.DataflowServiceStub(channel)
        request = dataflow_pb2.GetCollectionRequest(collection_name=collection_name)  # type: ignore
        response_iterator = stub.GetCollection(request)

        async for response in response_iterator:
            yield response.row


async def run_server() -> None:
    server = grpc.aio.server()
    dataflow_pb2_grpc.add_IEFunctionServiceServicer_to_server(
        IEFunctionService(), server
    )

    server.add_insecure_port(config.LISTEN_ADDRESS)
    await server.start()
    await server.wait_for_termination()  # Keep the server running


if __name__ == "__main__":
    asyncio.run(run_server())
