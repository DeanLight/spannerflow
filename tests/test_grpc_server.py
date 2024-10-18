from unittest.mock import AsyncMock, MagicMock

import grpc
import pytest

from spannerflow.dataflow.v1 import dataflow_pb2
from spannerflow.grpc_server import IEFunctionService


@pytest.mark.asyncio
async def test_run_ie_function():
    ie_functions = {
        "test_func": ("test_func", lambda x: [(int(x[0]) * 2)], [int], [int])
    }
    service = IEFunctionService(ie_functions)

    # Mock the request iterator
    request_iterator = AsyncMock()
    request_iterator.__aiter__.return_value = [
        dataflow_pb2.RunIEFunctionRequest(function_name="test_func"),
        dataflow_pb2.RunIEFunctionRequest(row=dataflow_pb2.RowRequest(row=["1"])),
        dataflow_pb2.RunIEFunctionRequest(row=dataflow_pb2.RowRequest(row=["2"])),
    ]

    # Mock the context
    context = MagicMock()

    # Collect the responses
    responses = []
    async for response in service.RunIEFunction(request_iterator, context):
        responses.append(response)

    # Assertions
    assert len(responses) == 2
    assert responses[0].row == ["2"]
    assert responses[1].row == ["4"]


@pytest.mark.asyncio
async def test_run_ie_function_not_found():
    ie_functions = {}
    service = IEFunctionService(ie_functions)

    # Mock the request iterator
    request_iterator = AsyncMock()
    request_iterator.__aiter__.return_value = [
        dataflow_pb2.RunIEFunctionRequest(function_name="unknown_func")
    ]

    # Mock the context
    context = MagicMock()

    # Collect the responses
    responses = []
    async for response in service.RunIEFunction(request_iterator, context):
        responses.append(response)

    # Assertions
    context.set_details.assert_called_once_with("IE Function 'unknown_func' not found.")
    context.set_code.assert_called_once_with(grpc.StatusCode.NOT_FOUND)
    assert len(responses) == 0


@pytest.mark.asyncio
async def test_run_ie_function_no_function_name():
    ie_functions = {
        "test_func": ("description", lambda x: [str(int(x) * 2)], [int], [int])
    }
    service = IEFunctionService(ie_functions)

    # Mock the request iterator
    request_iterator = AsyncMock()
    request_iterator.__aiter__.return_value = []

    # Mock the context
    context = MagicMock()

    # Collect the responses
    responses = []
    async for response in service.RunIEFunction(request_iterator, context):
        responses.append(response)

    # Assertions
    context.set_details.assert_called_once_with("No function name provided.")
    context.set_code.assert_called_once_with(grpc.StatusCode.INVALID_ARGUMENT)
    assert len(responses) == 0


@pytest.mark.asyncio
async def test_run_ie_function_function_name_after_rows():
    ie_functions = {
        "test_func": ("description", lambda x: [str(int(x) * 2)], [int], [int])
    }
    service = IEFunctionService(ie_functions)

    # Mock the request iterator
    request_iterator = AsyncMock()
    request_iterator.__aiter__.return_value = [
        dataflow_pb2.RunIEFunctionRequest(row=dataflow_pb2.RowRequest(row=["1"])),
        dataflow_pb2.RunIEFunctionRequest(function_name="test_func"),
    ]

    # Mock the context
    context = MagicMock()

    # Collect the responses
    responses = []
    async for response in service.RunIEFunction(request_iterator, context):
        responses.append(response)

    # Assertions
    context.set_details.assert_called_once_with(
        "Function name must be provided before rows."
    )
    context.set_code.assert_called_once_with(grpc.StatusCode.INVALID_ARGUMENT)
    assert len(responses) == 0


@pytest.mark.asyncio
async def test_run_ie_function_multiple_function_name():
    ie_functions = {
        "test_func": ("description", lambda x: [str(int(x) * 2)], [int], [int])
    }
    service = IEFunctionService(ie_functions)

    # Mock the request iterator
    request_iterator = AsyncMock()
    request_iterator.__aiter__.return_value = [
        dataflow_pb2.RunIEFunctionRequest(function_name="test_func"),
        dataflow_pb2.RunIEFunctionRequest(row=dataflow_pb2.RowRequest(row=["1"])),
        dataflow_pb2.RunIEFunctionRequest(function_name="test_func"),
    ]

    # Mock the context
    context = MagicMock()

    # Collect the responses
    responses = []
    async for response in service.RunIEFunction(request_iterator, context):
        responses.append(response)

    # Assertions
    context.set_details.assert_called_once_with("Function name already provided.")
    context.set_code.assert_called_once_with(grpc.StatusCode.INVALID_ARGUMENT)
    assert len(responses) == 0
