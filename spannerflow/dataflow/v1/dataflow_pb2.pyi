from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DataType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DATA_TYPE_UNSPECIFIED: _ClassVar[DataType]
    DATA_TYPE_STRING: _ClassVar[DataType]
    DATA_TYPE_INT: _ClassVar[DataType]
    DATA_TYPE_FLOAT: _ClassVar[DataType]
    DATA_TYPE_BOOL: _ClassVar[DataType]
DATA_TYPE_UNSPECIFIED: DataType
DATA_TYPE_STRING: DataType
DATA_TYPE_INT: DataType
DATA_TYPE_FLOAT: DataType
DATA_TYPE_BOOL: DataType

class RunIEFunctionRequest(_message.Message):
    __slots__ = ("function_name", "row")
    FUNCTION_NAME_FIELD_NUMBER: _ClassVar[int]
    ROW_FIELD_NUMBER: _ClassVar[int]
    function_name: str
    row: RowRequest
    def __init__(self, function_name: _Optional[str] = ..., row: _Optional[_Union[RowRequest, _Mapping]] = ...) -> None: ...

class RowRequest(_message.Message):
    __slots__ = ("row",)
    ROW_FIELD_NUMBER: _ClassVar[int]
    row: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, row: _Optional[_Iterable[str]] = ...) -> None: ...

class RunIEFunctionResponse(_message.Message):
    __slots__ = ("row",)
    ROW_FIELD_NUMBER: _ClassVar[int]
    row: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, row: _Optional[_Iterable[str]] = ...) -> None: ...

class LoadFromCSVRequest(_message.Message):
    __slots__ = ("collection_name", "file_path")
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    FILE_PATH_FIELD_NUMBER: _ClassVar[int]
    collection_name: str
    file_path: str
    def __init__(self, collection_name: _Optional[str] = ..., file_path: _Optional[str] = ...) -> None: ...

class SaveToCSVRequest(_message.Message):
    __slots__ = ("collection_name", "file_path")
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    FILE_PATH_FIELD_NUMBER: _ClassVar[int]
    collection_name: str
    file_path: str
    def __init__(self, collection_name: _Optional[str] = ..., file_path: _Optional[str] = ...) -> None: ...

class GetCollectionRequest(_message.Message):
    __slots__ = ("collection_name",)
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    collection_name: str
    def __init__(self, collection_name: _Optional[str] = ...) -> None: ...

class GetCollectionResponse(_message.Message):
    __slots__ = ("row",)
    ROW_FIELD_NUMBER: _ClassVar[int]
    row: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, row: _Optional[_Iterable[str]] = ...) -> None: ...

class AddRowRequest(_message.Message):
    __slots__ = ("collection_name", "row")
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    ROW_FIELD_NUMBER: _ClassVar[int]
    collection_name: str
    row: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, collection_name: _Optional[str] = ..., row: _Optional[_Iterable[str]] = ...) -> None: ...

class DeleteRowRequest(_message.Message):
    __slots__ = ("collection_name", "row")
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    ROW_FIELD_NUMBER: _ClassVar[int]
    collection_name: str
    row: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, collection_name: _Optional[str] = ..., row: _Optional[_Iterable[str]] = ...) -> None: ...

class AddCollectionRequest(_message.Message):
    __slots__ = ("collection_name", "schema")
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    SCHEMA_FIELD_NUMBER: _ClassVar[int]
    collection_name: str
    schema: _containers.RepeatedScalarFieldContainer[DataType]
    def __init__(self, collection_name: _Optional[str] = ..., schema: _Optional[_Iterable[_Union[DataType, str]]] = ...) -> None: ...

class Collection(_message.Message):
    __slots__ = ("name", "schema")
    NAME_FIELD_NUMBER: _ClassVar[int]
    SCHEMA_FIELD_NUMBER: _ClassVar[int]
    name: str
    schema: _containers.RepeatedScalarFieldContainer[DataType]
    def __init__(self, name: _Optional[str] = ..., schema: _Optional[_Iterable[_Union[DataType, str]]] = ...) -> None: ...

class GetCollectionsResponse(_message.Message):
    __slots__ = ("collections",)
    COLLECTIONS_FIELD_NUMBER: _ClassVar[int]
    collections: _containers.RepeatedCompositeFieldContainer[Collection]
    def __init__(self, collections: _Optional[_Iterable[_Union[Collection, _Mapping]]] = ...) -> None: ...

class DeleteCollectionRequest(_message.Message):
    __slots__ = ("collection_name",)
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    collection_name: str
    def __init__(self, collection_name: _Optional[str] = ...) -> None: ...

class RunDataflowRequest(_message.Message):
    __slots__ = ("so_path", "fn_name")
    SO_PATH_FIELD_NUMBER: _ClassVar[int]
    FN_NAME_FIELD_NUMBER: _ClassVar[int]
    so_path: str
    fn_name: str
    def __init__(self, so_path: _Optional[str] = ..., fn_name: _Optional[str] = ...) -> None: ...

class RunDataflowResponse(_message.Message):
    __slots__ = ("row",)
    ROW_FIELD_NUMBER: _ClassVar[int]
    row: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, row: _Optional[_Iterable[str]] = ...) -> None: ...
