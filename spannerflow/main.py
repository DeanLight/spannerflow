import asyncio
import inspect
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Generator, Iterable

import grpc
import jinja2
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
    TEMPLATES_PATH: Path = Path("templates")
    CARGO_TOML_TEMPLATE_NAME: str = "Cargo.toml.jinja2"
    RUST_FILE_TEMPLATE_NAME: str = "rust_test.rs.jinja2"
    RUST_BUILD_TEMPLATE_NAME: str = "build.rs.jinja2"
    RUST_PROJECT_NAME: str = "spannerflow"
    RUST_DEPENDENCIES: list[dict[str, str]] = field(
        default_factory=lambda: [
            {"name": "timely", "version": "0.12.0"},
            {"name": "differential-dataflow", "version": "0.12.0"},
            {"name": "prost", "version": "0.13.3"},
            {"name": "prost-types", "version": "0.13.3"},
        ]
    )
    RUST_BUILD_DEPEDENCIES: list[dict[str, str]] = field(
        default_factory=lambda: [
            {"name": "prost-build", "version": "0.13.3"},
        ]
    )
    PROTO_DIR_PATH: Path = Path("./proto").absolute()
    PROTO_FILE_PATH: Path = PROTO_DIR_PATH.joinpath("dataflow", "v1", "dataflow.proto")


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


def create_cargo_toml(file_name: str, timestamp: str) -> None:
    dest_path = config.GENERATED_RUST_PROJECT_PATH / file_name
    template_loader = jinja2.FileSystemLoader(searchpath=config.TEMPLATES_PATH)
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(config.CARGO_TOML_TEMPLATE_NAME)

    output_text = template.render(
        project_name=config.RUST_PROJECT_NAME,
        rust_file_name=f"{timestamp}.rs",
        dependencies=config.RUST_DEPENDENCIES,
        build_dependencies=config.RUST_BUILD_DEPEDENCIES,
    )

    with open(dest_path, "w") as f:
        f.write(output_text)


def create_rust_file(timestamp: str) -> None:
    dest_path = config.GENERATED_RUST_PROJECT_PATH / "src" / f"{timestamp}.rs"
    template_loader = jinja2.FileSystemLoader(searchpath=config.TEMPLATES_PATH)
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(config.RUST_FILE_TEMPLATE_NAME)

    output_text = template.render()

    with open(dest_path, "w") as f:
        f.write(output_text)


def create_rust_build_file(proto_dir_path: Path, proto_file_path: Path) -> None:
    dest_path = config.GENERATED_RUST_PROJECT_PATH / "build.rs"
    template_loader = jinja2.FileSystemLoader(searchpath=config.TEMPLATES_PATH)
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(config.RUST_BUILD_TEMPLATE_NAME)

    output_text = template.render(
        proto_dir_path=proto_dir_path, proto_file_path=proto_file_path
    )

    with open(dest_path, "w") as f:
        f.write(output_text)


def build_so() -> None:
    config.GENERATED_RUST_PROJECT_PATH.joinpath("src").mkdir(
        parents=True, exist_ok=True
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cargo_file_name = "Cargo.toml"
    create_cargo_toml(cargo_file_name, timestamp)
    create_rust_file(timestamp)
    create_rust_build_file(config.PROTO_DIR_PATH, config.PROTO_FILE_PATH)
    build_rust(config.GENERATED_RUST_PROJECT_PATH.joinpath(cargo_file_name).absolute())


def build_rust(cargo_toml_path: Path) -> None:
    command = [
        "cargo",
        "build",
        "--release",
        "--manifest-path",
        str(cargo_toml_path),
    ]
    subprocess.run(
        command,
        cwd=str(cargo_toml_path.parent),
        check=True,
    )


class IEFunctionService(dataflow_pb2_grpc.IEFunctionServiceServicer):
    async def RunIEFunction(
        self,
        request: dataflow_pb2.RunIEFunctionRequest,
        context,  # type: ignore
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


def build_rust_server() -> None:
    cargo_toml_path = Path(__file__).parent.joinpath("Cargo.toml")
    build_rust(cargo_toml_path.absolute())


async def serve() -> None:
    server = grpc.aio.server()
    dataflow_pb2_grpc.add_IEFunctionServiceServicer_to_server(
        IEFunctionService(), server
    )

    server.add_insecure_port(config.LISTEN_ADDRESS)
    await server.start()
    await server.wait_for_termination()  # Keep the server running


@contextmanager
def run_rust_server_in_background() -> Generator[None, None, None]:
    # TODO: handle port is already in use
    server_path = (
        Path(__file__)
        .parent.joinpath("target", "release", "spannerflow_rust")
        .absolute()
    )
    with open("process.log", "a") as log_file:
        process = subprocess.Popen([str(server_path)], stdout=log_file, stderr=log_file)
        try:
            yield
        finally:
            process.terminate()
            process.wait()


if __name__ == "__main__":
    build_rust_server()
    build_so()
    with run_rust_server_in_background():
        asyncio.run(serve())
