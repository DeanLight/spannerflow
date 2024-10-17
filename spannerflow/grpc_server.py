import asyncio
from typing import Any, AsyncGenerator, Callable

import grpc

from spannerflow.config import Config
from spannerflow.dataflow.v1 import dataflow_pb2, dataflow_pb2_grpc

config = Config()


class IEFunctionService(dataflow_pb2_grpc.IEFunctionServiceServicer):
    def __init__(
        self,
        ie_functions: dict[
            str, tuple[str, Callable[[Any], Any], list[type], list[type]]
        ],
    ):
        super().__init__()
        self._ie_functions = ie_functions

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
                func_tuple = self._ie_functions.get(function_name)

                if func_tuple is None:
                    context.set_details(f"IE Function '{function_name}' not found.")
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    return  # Return early after setting the error
                func = func_tuple[1]

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


async def run_server(
    ie_functions: dict[str, tuple[str, Callable[[Any], Any], list[type], list[type]]],
) -> None:
    server = grpc.aio.server()
    dataflow_pb2_grpc.add_IEFunctionServiceServicer_to_server(
        IEFunctionService(ie_functions), server
    )

    server.add_insecure_port(config.LISTEN_ADDRESS)
    await server.start()
    await server.wait_for_termination()  # Keep the server running


if __name__ == "__main__":
    asyncio.run(run_server(dict()))
