import asyncio
import inspect
from typing import AsyncGenerator

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
def sync_greet(rows: list[list[str]]) -> list[list[str]]:
    for row in rows:
        row += ["Hello, World!"]
    return rows


## Example Functions End ##


class IEFunctionService(dataflow_pb2_grpc.IEFunctionServiceServicer):
    async def RunIEFunction(
        self,
        request_iterator: AsyncGenerator[dataflow_pb2.RunIEFunctionRequest, None],  # type: ignore
        context,
    ) -> AsyncGenerator[dataflow_pb2.RunIEFunctionResponse, None]:  # type: ignore
        function_name = None
        func = None
        rows = []
        async for request in request_iterator:
            if request.HasField("function_name"):
                # Extract the function_name from the first request
                function_name = request.function_name
                func = _IE_FUNCTIONS.get(function_name)

                if func is None:
                    context.set_details(f"IE Function '{function_name}' not found.")
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return  # Return early after setting the error

            elif request.HasField("row"):
                if func is None:
                    context.set_details("Function name must be provided before rows.")
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    return  # Function name must come first

                rows.append([str(row) for row in request.row.row])

        if function_name is None or func is None:
            context.set_details("No function name provided.")
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return

        for row in func(rows):
            response = dataflow_pb2.RunIEFunctionResponse(  # type: ignore
                row=[str(cell) for cell in row]
            )
            yield response


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
