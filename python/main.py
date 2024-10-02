import asyncio
import inspect
import jinja2
import subprocess
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
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
    GENERATED_RUST_PROJECT_PATH: Path = Path("generated_rust")


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


## Example Functions Start ##
@register_function
async def async_greet(rows: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    async for row in rows:
        yield f"Hello, World! {row}"


@register_function
def sync_greet(rows: Generator[str, None, None]) -> Generator[str, None, None]:
    for row in rows:
        yield f"Hello, World! {row}"
## Example Functions End ##



def create_cargo_toml(file_name: str, timestamp: str) -> None:
    # Define project name and dependencies
    dest_path = Config.GENERATED_RUST_PROJECT_PATH / file_name
    dependencies = [
        {"name": "timely", "version": "0.12.0"},  # Check for the latest version
        {"name": "differential-dataflow", "version": "0.12.0"},
    ]

    # Load the Jinja2 template
    template_loader = jinja2.FileSystemLoader(searchpath="./templates")
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template("Cargo.toml.jinja2")

    # Render the template with context
    output_text = template.render(project_name="spannerflow", 
                                  rust_file_name=f"{timestamp}.rs",
                                  dependencies=dependencies)

    # Write the output to Cargo.toml
    with open(dest_path, "w") as f:
        f.write(output_text)

def create_rust_file(timestamp: str) -> None:
    # Define project name and dependencies
    dest_path = Config.GENERATED_RUST_PROJECT_PATH / "src" / f"{timestamp}.rs"
    template_loader = jinja2.FileSystemLoader(searchpath="./templates")
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template("rust_test.rs.jinja2")

    # Render the template with context
    output_text = template.render()

    # Write the output to Cargo.toml
    with open(dest_path, "w") as f:
        f.write(output_text)
    
def build_so() -> None:
    Config.GENERATED_RUST_PROJECT_PATH.joinpath("src").mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cargo_file_name = f"Cargo.toml"
    create_cargo_toml(cargo_file_name, timestamp)
    create_rust_file(timestamp)
    command =  [
            "cargo",
            "build",
            "--release",
            "--manifest-path",
            str(Config.GENERATED_RUST_PROJECT_PATH.joinpath(cargo_file_name).absolute()),
        ]
    print(command)
    subprocess.run(
       command,
       cwd=str(Config.GENERATED_RUST_PROJECT_PATH),
    )

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
    # asyncio.run(serve())
    build_so()
