import glob
import os
from pathlib import Path

from spannerflow.dataflow.v1 import dataflow_pb2
from spannerflow.engine import Engine
from spannerflow.installations import install_protoc, install_rust

# TODO: instead of building wheel artifacts, allow pip install with url to repo without maintaining a registry
install_protoc()
extract_dir = Path("protoc").absolute()
protoc_bin_path = extract_dir.joinpath("bin")
os.environ["PATH"] = os.pathsep.join([str(protoc_bin_path), os.environ["PATH"]])
# TODO: add binraies as library entrypoints instead of modifying PATH
install_rust()
extract_dir = Path("rust").absolute()
dirs = glob.glob(f"{extract_dir}/*/*/bin")
os.environ["PATH"] = os.pathsep.join(dirs + [os.environ["PATH"]])


__all__ = ["Engine", "dataflow_pb2"]
