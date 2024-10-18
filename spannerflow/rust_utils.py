import subprocess
from pathlib import Path

from spannerflow.config import Config

config = Config()


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
