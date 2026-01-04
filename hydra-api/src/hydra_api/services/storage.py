"""Object storage service for agent binary distribution.

Provides S3-compatible storage (Garage/MinIO/AWS S3) using the Minio SDK.
S3 is the single source of truth for agent binaries.
"""

import asyncio
import json
from functools import partial
from typing import TYPE_CHECKING, AsyncIterator
from urllib.parse import urlparse

import structlog

if TYPE_CHECKING:
    from hydra_api.core.config import Settings

logger = structlog.get_logger(__name__)


class StorageError(Exception):
    """Base exception for storage errors."""

    pass


class ObjectNotFoundError(StorageError):
    """Object not found in storage."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"Object not found: {key}")


class StorageUnavailableError(StorageError):
    """Storage service is unavailable."""

    def __init__(self, message: str = "Storage service unavailable"):
        super().__init__(message)


class StorageNotConfiguredError(StorageError):
    """Storage service is not configured."""

    def __init__(self):
        super().__init__(
            "Object storage is not configured. "
            "Set HYDRA_OBJECT_STORAGE_ENABLED=true and provide S3 credentials."
        )


class StorageService:
    """S3-compatible storage service using the Minio SDK (works with Garage/MinIO/S3)."""

    def __init__(self, settings: "Settings"):
        from minio import Minio
        from minio.error import S3Error

        self.bucket = settings.object_storage_bucket
        self._s3_error = S3Error

        # Parse endpoint URL to extract host and determine if secure
        endpoint_url = settings.object_storage_endpoint
        parsed = urlparse(endpoint_url)
        endpoint = parsed.netloc or parsed.path
        secure = parsed.scheme == "https"

        logger.info(
            "initializing_s3_storage",
            endpoint=endpoint,
            bucket=self.bucket,
            secure=secure,
            region=settings.object_storage_region,
        )

        self._client = Minio(
            endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            secure=secure,
            region=settings.object_storage_region,
        )

    def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous minio operation in a thread pool."""
        return asyncio.get_event_loop().run_in_executor(
            None, partial(func, *args, **kwargs)
        )

    async def get_object_stream(self, key: str) -> AsyncIterator[bytes]:
        """Stream object content from S3."""
        logger.debug("s3_get_object_stream", key=key, bucket=self.bucket)
        try:
            response = await self._run_sync(
                self._client.get_object, self.bucket, key
            )
            try:
                # Read in chunks
                chunk_size = 64 * 1024  # 64KB
                while True:
                    chunk = await asyncio.get_event_loop().run_in_executor(
                        None, response.read, chunk_size
                    )
                    if not chunk:
                        break
                    yield chunk
            finally:
                response.close()
                response.release_conn()
        except self._s3_error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(key)
            logger.error("s3_get_object_failed", key=key, error=str(e))
            raise StorageUnavailableError(f"Failed to get object: {e}")
        except Exception as e:
            logger.error("s3_get_object_failed", key=key, error=str(e))
            raise StorageUnavailableError(f"Failed to get object: {e}")

    async def get_object_metadata(self, key: str) -> dict:
        """Get object metadata from S3."""
        try:
            # Try to get metadata.json for the version
            metadata_key = key.rsplit("/", 1)[0] + "/metadata.json"
            try:
                response = await self._run_sync(
                    self._client.get_object, self.bucket, metadata_key
                )
                try:
                    body = response.read()
                    metadata = json.loads(body.decode("utf-8"))
                    return metadata
                finally:
                    response.close()
                    response.release_conn()
            except Exception:
                pass

            # Fall back to stat_object for basic metadata
            stat = await self._run_sync(
                self._client.stat_object, self.bucket, key
            )
            return {
                "size": stat.size,
                "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                "etag": stat.etag.strip('"') if stat.etag else None,
            }
        except self._s3_error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(key)
            logger.error("s3_head_object_failed", key=key, error=str(e))
            raise StorageUnavailableError(f"Failed to get metadata: {e}")
        except ObjectNotFoundError:
            raise
        except Exception as e:
            logger.error("s3_head_object_failed", key=key, error=str(e))
            raise StorageUnavailableError(f"Failed to get metadata: {e}")

    async def list_versions(self, target: str) -> list[dict]:
        """List available versions for a target from S3."""
        versions = []
        prefix = f"agents/{target}/"

        logger.debug("s3_list_versions", target=target, prefix=prefix, bucket=self.bucket)

        try:
            # List objects with prefix recursively to find all version directories
            # We need recursive=True because Minio's recursive=False behavior
            # doesn't reliably return "directory" markers for all S3-compatible stores
            def _list_objects():
                return list(self._client.list_objects(
                    self.bucket, prefix=prefix, recursive=True
                ))

            objects = await self._run_sync(_list_objects)
            print(objects)
            logger.debug("s3_list_objects_result", target=target, object_count=len(objects))

            seen_versions = set()
            for obj in objects:
                # Extract version from path (format: agents/{target}/{version}/hydra-agent)
                name = obj.object_name
                logger.debug("s3_object_found", object_name=name)

                if name.startswith(prefix):
                    remainder = name[len(prefix):]
                    # Get the version from the path segment
                    parts = remainder.split("/")
                    if len(parts) >= 1:
                        version = parts[0]
                        # Valid versions start with a digit, skip 'latest' marker
                        if version and version != "latest" and version[0].isdigit():
                            if version not in seen_versions:
                                seen_versions.add(version)
                                versions.append({"version": version})

            # Sort by version (semantic versioning)
            versions.sort(
                key=lambda v: [
                    int(x) if x.isdigit() else 0
                    for x in v["version"].replace("-", ".").split(".")
                ],
                reverse=True,
            )

            logger.info("s3_versions_found", target=target, version_count=len(versions))
            return versions[:15]  # Return max 15 versions

        except Exception as e:
            logger.error("s3_list_versions_failed", target=target, prefix=prefix, error=str(e))
            raise StorageUnavailableError(f"Failed to list versions: {e}")

    async def get_latest_version(self, target: str) -> str | None:
        """Get the latest version for a target from S3."""
        latest_key = f"agents/{target}/latest"

        try:
            response = await self._run_sync(
                self._client.get_object, self.bucket, latest_key
            )
            try:
                body = response.read()
                return body.decode("utf-8").strip()
            finally:
                response.close()
                response.release_conn()
        except Exception:
            # Fall back to listing versions
            versions = await self.list_versions(target)
            return versions[0]["version"] if versions else None

    async def object_exists(self, key: str) -> bool:
        """Check if object exists in S3."""
        try:
            await self._run_sync(self._client.stat_object, self.bucket, key)
            return True
        except Exception:
            return False

    async def health_check(self) -> bool:
        """Check S3 connectivity."""
        try:
            exists = await self._run_sync(self._client.bucket_exists, self.bucket)
            logger.debug("s3_health_check", bucket=self.bucket, exists=exists)
            return exists
        except Exception as e:
            logger.warning("s3_health_check_failed", error=str(e))
            return False


# Global instance cache
_storage_service: StorageService | None = None


def get_storage_service(settings: "Settings") -> StorageService:
    """
    Factory function to get the storage service.

    Requires S3 storage to be configured.
    """
    if not settings.has_object_storage:
        raise StorageNotConfiguredError()

    logger.info(
        "creating_storage_service",
        endpoint=settings.object_storage_endpoint,
        bucket=settings.object_storage_bucket,
    )
    return StorageService(settings)


def get_cached_storage_service(settings: "Settings") -> StorageService | None:
    """Get or create cached storage service instance.

    Returns None if storage is not configured.
    """
    global _storage_service

    if not settings.has_object_storage:
        logger.debug("storage_not_configured")
        return None

    if _storage_service is None:
        _storage_service = get_storage_service(settings)
    return _storage_service
