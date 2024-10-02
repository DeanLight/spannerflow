# To generate protos:

```bash
python -m grpc_tools.protoc -I../proto --python_out=. --grpc_python_out=. ../proto/dataflow/v1/dataflow.proto
```