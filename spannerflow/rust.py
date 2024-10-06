import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

import jinja2

from spannerflow.config import Config

config = Config()


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
    build_rust(
        config.GENERATED_RUST_PROJECT_PATH.joinpath(cargo_file_name).absolute(),
        config.RUST_SO_BUILD_LOG_PATH,
    )


def build_rust(cargo_toml_path: Path, log_path: Path) -> None:
    command = [
        "cargo",
        "build",
        "--release",
        "--manifest-path",
        str(cargo_toml_path),
    ]

    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as log_file:
        subprocess.run(
            command,
            cwd=str(cargo_toml_path.parent),
            check=True,
            stderr=log_file,
            stdout=log_file,
        )


def build_rust_server() -> None:
    cargo_toml_path = Path(__file__).parent.joinpath("Cargo.toml")
    build_rust(cargo_toml_path.absolute(), config.RUST_SERVER_BUILD_LOG_PATH)


@contextmanager
def run_rust_server_in_background() -> Generator[None, None, None]:
    # TODO: handle port is already in use
    server_path = (
        Path(__file__)
        .parent.joinpath("target", "release", "spannerflow_rust")
        .absolute()
    )
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.RUST_SERVER_LOG_PATH, "a") as log_file:
        process = subprocess.Popen([str(server_path)], stdout=log_file, stderr=log_file)
        try:
            yield
        finally:
            process.terminate()
            process.wait()
