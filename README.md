# spannerflow

```bash
python -m venv venv
source venv/bin/activate
pip install poetry
poetry install
pre-commit install

cd spannerflow/proto
python -m grpc_tools.protoc -I. --python_out=.. --pyi_out=.. --grpc_python_out=.. ./dataflow/v1/dataflow.proto
# TODO: Patch imports and ignore mypy on generated files
cd ../..
pre-commit run --all-files
poetry build
```
