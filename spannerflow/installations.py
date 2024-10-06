import os
import platform
import subprocess
import zipfile

import requests


def check_for_protoc() -> bool:
    try:
        subprocess.run(["protoc", "--version"], check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def install_protoc() -> None:
    if check_for_protoc():
        print("protoc is already installed.")
        return

    # Mapping of platform.system() to OS name in the download URL
    operation_systems = {"Linux": "linux", "Darwin": "osx", "Windows": "win"}

    # Mapping of platform.machine() to architecture name in the download URL
    architecture = {
        "s390x": "s390_64",
        "aarch64": "aarch_64",
        "arm64": "aarch_64",
        "ppc64le": "ppcle_64",
        "x86_64": "x86_64",
        "i386": "x86_32",
        "AMD64": "win64",  # Standard Windows 64-bit architecture
        "x86": "win32",  # Standard Windows 32-bit architecture
    }

    operation_system = operation_systems.get(platform.system(), None)
    arch = architecture.get(platform.machine(), None)

    if not os or not arch:
        print("Unsupported operating system or architecture.")
        return

    if operation_system == "win":
        # For Windows, the file naming convention is `protoc-28.2-win32.zip` or `protoc-28.2-win64.zip`
        operation_system_and_arch = f"{arch}"
    else:
        # For other systems, the naming convention includes both OS and architecture
        operation_system_and_arch = f"{operation_system}-{arch}"

    url = f"https://github.com/protocolbuffers/protobuf/releases/download/v28.2/protoc-28.2-{operation_system_and_arch}.zip"

    # Download the file
    response = requests.get(url, stream=True)
    zip_filename = "protoc.zip"
    if response.status_code == 200:
        with open(zip_filename, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"Downloaded protoc successfully from {url}.")
    else:
        print(f"Failed to download protoc. HTTP status code: {response.status_code}")
        return
    extract_dir = "protoc"
    with zipfile.ZipFile(zip_filename, "r") as zip_ref:
        zip_ref.extractall(extract_dir)
    print(f"Extracted protoc files to {extract_dir}.")

    os.remove(zip_filename)
    print(f"Removed the zip file: {zip_filename}")
    protoc_bin_path = os.path.abspath(os.path.join(extract_dir, "bin"))
    protoc_path = os.path.abspath(os.path.join(protoc_bin_path, "protoc"))
    os.chmod(protoc_path, 0o755)
    os.environ["PATH"] = protoc_bin_path + os.pathsep + os.environ["PATH"]
