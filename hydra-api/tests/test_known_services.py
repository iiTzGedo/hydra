"""Tests for known services registry service."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.services import KnownServiceCreateRequest, ServiceRuntime
from hydra.api.v1.services.known_services import KnownServicesService
from tests.utils import create_mock_cursor


@pytest.fixture
def mongodb_mock():
    db = MagicMock()
    db.known_services = MagicMock()
    db.known_services.find_one = AsyncMock(return_value=None)
    db.known_services.insert_one = AsyncMock()
    db.known_services.delete_one = AsyncMock()
    db.known_services.count_documents = AsyncMock(return_value=0)
    db.known_services.find = MagicMock(return_value=create_mock_cursor([]))
    return db


def test_normalize_name_trims_and_lowercases(mongodb_mock):
    service = KnownServicesService(mongodb_mock)
    assert service._normalize_name("  NGINX  ") == "nginx"


@pytest.mark.asyncio
async def test_list_known_services_with_filters(mongodb_mock):
    now = datetime.now(UTC)
    docs = [
        {
            "knownServiceId": "ksvc_1",
            "runtime": "docker",
            "name": "nginx",
            "description": "web",
            "tags": ["proxy"],
            "createdAt": now,
            "updatedAt": now,
            "createdBy": "user_1",
        }
    ]
    mongodb_mock.known_services.count_documents = AsyncMock(return_value=1)
    mongodb_mock.known_services.find = MagicMock(return_value=create_mock_cursor(docs))

    service = KnownServicesService(mongodb_mock)
    results, total = await service.list_known_services(
        runtime="docker",
        search="nginx",
        limit=10,
        offset=5,
    )

    assert total == 1
    assert len(results) == 1
    assert results[0]["knownServiceId"] == "ksvc_1"

    query = mongodb_mock.known_services.count_documents.await_args.args[0]
    assert query["runtime"] == "docker"
    assert "$or" in query


@pytest.mark.asyncio
async def test_create_known_service_success(mongodb_mock):
    service = KnownServicesService(mongodb_mock)
    request = KnownServiceCreateRequest(
        runtime=ServiceRuntime.DOCKER,
        name="Nginx",
        description="Web server",
        tags=["proxy"],
    )

    result = await service.create_known_service(request, created_by="user_1")

    assert result["runtime"] == "docker"
    assert result["name"] == "Nginx"
    assert result["createdBy"] == "user_1"
    assert result["knownServiceId"].startswith("ksvc_")
    mongodb_mock.known_services.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_known_service_duplicate_raises_validation_error(mongodb_mock):
    mongodb_mock.known_services.find_one = AsyncMock(
        return_value={"knownServiceId": "ksvc_existing"}
    )
    service = KnownServicesService(mongodb_mock)
    request = KnownServiceCreateRequest(
        runtime=ServiceRuntime.DOCKER,
        name="nginx",
        description=None,
        tags=[],
    )

    with pytest.raises(ValidationError):
        await service.create_known_service(request)


@pytest.mark.asyncio
async def test_delete_known_service_success(mongodb_mock):
    now = datetime.now(UTC)
    existing = {
        "knownServiceId": "ksvc_1",
        "runtime": "docker",
        "name": "nginx",
        "description": None,
        "tags": [],
        "createdAt": now,
        "updatedAt": now,
        "createdBy": "user_1",
    }
    mongodb_mock.known_services.find_one = AsyncMock(return_value=existing)

    service = KnownServicesService(mongodb_mock)
    result = await service.delete_known_service("ksvc_1")

    assert result["knownServiceId"] == "ksvc_1"
    mongodb_mock.known_services.delete_one.assert_awaited_once_with(
        {"knownServiceId": "ksvc_1"}
    )


@pytest.mark.asyncio
async def test_delete_known_service_not_found_raises(mongodb_mock):
    mongodb_mock.known_services.find_one = AsyncMock(return_value=None)
    service = KnownServicesService(mongodb_mock)

    with pytest.raises(NotFoundError):
        await service.delete_known_service("ksvc_missing")
