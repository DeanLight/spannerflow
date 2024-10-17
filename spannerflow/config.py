from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    LISTEN_PORT: int = 50052
    LISTEN_IP: str = "localhost"
    LISTEN_ADDRESS: str = f"{LISTEN_IP}:{LISTEN_PORT}"
    DATAFLOW_PORT: int = 50051
    DATAFLOW_IP: str = "localhost"
    DATAFLOW_ADDRESS: str = f"{DATAFLOW_IP}:{DATAFLOW_PORT}"
    GENERATED_RUST_PROJECT_PATH: Path = Path(__file__).parent.joinpath("generated_rust")
    TEMPLATES_PATH: Path = Path(__file__).parent.joinpath("templates")
    CARGO_TOML_TEMPLATE_NAME: str = "Cargo.toml.jinja2"
    RUST_FILE_TEMPLATE_NAME: str = "rust_dataflow.rs.jinja2"
    RUST_BUILD_TEMPLATE_NAME: str = "build.rs.jinja2"
    RUST_PROJECT_NAME: str = "spannerflow"
    RUST_DEPENDENCIES: list[dict[str, str]] = field(
        default_factory=lambda: [
            {"name": "timely", "version": "0.12.0"},
            {"name": "differential-dataflow", "version": "0.12.0"},
            {"name": "prost", "version": "0.13.3"},
            {"name": "prost-types", "version": "0.13.3"},
            {"name": "tonic", "version": "0.12.3"},
            {"name": "ordered-float", "version": "4.4.0"},
            {"name": "tokio", "json": '{ version = "1.40.0", features = ["full"] }'},
            {"name": "futures", "version": "0.3.31"},
        ]
    )
    RUST_BUILD_DEPEDENCIES: list[dict[str, str]] = field(
        default_factory=lambda: [
            {"name": "tonic-build", "version": "0.12.3"},
        ]
    )
    PROTO_DIR_PATH: Path = Path(__file__).parent.joinpath("proto").absolute()
    PROTO_FILE_PATH: Path = PROTO_DIR_PATH.joinpath("dataflow", "v1", "dataflow.proto")
    LOGS_DIR: Path = Path(__file__).parent.joinpath("logs")
    RUST_SERVER_LOG_PATH: Path = LOGS_DIR.joinpath("rust_server.log")
    RUST_SERVER_BUILD_LOG_PATH: Path = LOGS_DIR.joinpath("rust_server_build.log")
    RUST_SO_BUILD_LOG_PATH: Path = LOGS_DIR.joinpath("rust_so_build.log")
