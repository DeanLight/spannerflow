# spannerflow

```bash
python -m venv venv
source venv/bin/activate
pip install poetry
poetry install
pre-commit install

python -m grpc_tools.protoc -I./proto --python_out=./spannerflow --grpc_python_out=./spannerflow ./spannerflow/proto/dataflow/v1/dataflow.proto

pre-commit run --all-files
poetry build
```