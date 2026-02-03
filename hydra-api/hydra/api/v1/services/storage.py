"""Object storage service for agent binary and bundle distribution.

Supports multiple storage backends:
- S3-compatible storage (Garage/MinIO/AWS S3) for binaries and bundles
- Local filesystem storage for bundles

Storage layout:
- Binaries: agents/{target}/{version}/hydra-agent
- Bundles: bundles/{version}/hydra-agent-{version}.zip
"""

import asyncio
import json
import os
from abc import ABC, abstractmethod
from enum import Enum
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

import structlog

if TYPE_CHECKING:
    from hydra.core.config import Settings

logger = structlog.get_logger(__name__)


# =============================================================================
# Storage Source Enum
# =============================================================================

class StorageSource(str, Enum):
    """Available storage sources for agent distribution."""

    BINARY = "binary"  # Pre-compiled binaries from S3/Garage (default, fastest)
    OBS = "obs"        # Bundled source from S3/Garage (Object Storage)
    LOCAL = "local"    # Bundled source from local filesystem


# =============================================================================
# Exceptions
# =============================================================================

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


class InvalidStorageSourceError(StorageError):
    """Unknown storage source specified."""

    def __init__(self, source: str | StorageSource):
        self.source = source
        super().__init__(f"Unknown storage source: {source}")


class StorageNotConfiguredError(StorageError):
    """Storage service is not configured."""

    def __init__(self, source: StorageSource | None = None):
        if source == StorageSource.LOCAL:
            msg = (
                "Local storage is not configured. "
                "Set HYDRA_LOCAL_STORAGE_ENABLED=true and HYDRA_LOCAL_STORAGE_PATH."
            )
        elif source == StorageSource.OBS:
            msg = (
                "Object storage is not configured. "
                "Set HYDRA_OBJECT_STORAGE_ENABLED=true and provide S3 credentials."
            )
        else:
            msg = (
                "No storage is configured. "
                "Enable object storage (S3) or local storage for agent distribution."
            )
        super().__init__(msg)


# =============================================================================
# Abstract Base Class
# =============================================================================

class BaseStorageService(ABC):
    """Abstract base class for storage services."""

    @abstractmethod
    async def get_object_stream(self, key: str) -> AsyncIterator[bytes]:
        """Stream object content from storage."""
        pass

    @abstractmethod
    async def get_object_metadata(self, key: str) -> dict:
        """Get object metadata from storage."""
        pass

    @abstractmethod
    async def list_versions(self, target: str | None = None) -> list[dict]:
        """List available versions."""
        pass

    @abstractmethod
    async def get_latest_version(self, target: str | None = None) -> str | None:
        """Get the latest version."""
        pass

    @abstractmethod
    async def object_exists(self, key: str) -> bool:
        """Check if object exists."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check storage connectivity."""
        pass


# =============================================================================
# S3 Storage Service (for binaries)
# =============================================================================

class S3StorageService(BaseStorageService):
    """S3-compatible storage service using the Minio SDK (works with Garage/MinIO/S3)."""

    def __init__(self, settings: "Settings"):
        from minio import Minio
        from minio.error import S3Error
        from urllib.parse import urlparse

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

    async def list_versions(self, target: str | None = None) -> list[dict]:
        """List available versions for a target from S3."""
        versions = []
        prefix = f"agents/{target}/" if target else "agents/"

        logger.debug("s3_list_versions", target=target, prefix=prefix, bucket=self.bucket)

        try:
            def _list_objects():
                return list(self._client.list_objects(
                    self.bucket, prefix=prefix, recursive=True
                ))

            objects = await self._run_sync(_list_objects)
            logger.debug("s3_list_objects_result", target=target, object_count=len(objects))

            seen_versions = set()
            for obj in objects:
                name = obj.object_name
                logger.debug("s3_object_found", object_name=name)

                if name.startswith(prefix):
                    remainder = name[len(prefix):]
                    parts = remainder.split("/")
                    if len(parts) >= 1:
                        version = parts[0]
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

        except self._s3_error as e:
            logger.error("s3_list_versions_failed", target=target, prefix=prefix, error=str(e), error_type="s3_error")
            raise StorageUnavailableError(f"Failed to list versions: {e}")
        except Exception as e:
            logger.error("s3_list_versions_unexpected_error", target=target, prefix=prefix, error=str(e), error_type=type(e).__name__)
            raise StorageUnavailableError(f"Failed to list versions: {e}")

    async def get_latest_version(self, target: str | None = None) -> str | None:
        """Get the latest version for a target from S3."""
        if target:
            latest_key = f"agents/{target}/latest"
        else:
            latest_key = "agents/latest"

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


# =============================================================================
# S3 Bundle Storage Service (for source bundles in S3)
# =============================================================================

class S3BundleStorageService(S3StorageService):
    """S3 storage service specialized for source bundles."""

    async def list_versions(self, target: str | None = None) -> list[dict]:
        """List available bundle versions from S3."""
        versions = []
        prefix = "bundles/"

        logger.debug("s3_list_bundle_versions", prefix=prefix, bucket=self.bucket)

        try:
            def _list_objects():
                return list(self._client.list_objects(
                    self.bucket, prefix=prefix, recursive=True
                ))

            objects = await self._run_sync(_list_objects)
            logger.debug("s3_list_bundles_result", object_count=len(objects))

            seen_versions = set()
            for obj in objects:
                name = obj.object_name
                # Format: bundles/{version}/hydra-agent-{version}.zip
                if name.startswith(prefix) and name.endswith(".zip"):
                    remainder = name[len(prefix):]
                    parts = remainder.split("/")
                    if len(parts) >= 1:
                        version = parts[0]
                        if version and version[0].isdigit() and version not in seen_versions:
                            seen_versions.add(version)
                            versions.append({
                                "version": version,
                                "size": obj.size,
                                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                            })

            versions.sort(
                key=lambda v: [
                    int(x) if x.isdigit() else 0
                    for x in v["version"].replace("-", ".").split(".")
                ],
                reverse=True,
            )

            logger.info("s3_bundle_versions_found", version_count=len(versions))
            return versions[:15]

        except self._s3_error as e:
            logger.error("s3_list_bundle_versions_failed", prefix=prefix, error=str(e), error_type="s3_error")
            raise StorageUnavailableError(f"Failed to list bundle versions: {e}")
        except Exception as e:
            logger.error("s3_list_bundle_versions_unexpected_error", prefix=prefix, error=str(e), error_type=type(e).__name__)
            raise StorageUnavailableError(f"Failed to list bundle versions: {e}")

    async def get_latest_version(self, target: str | None = None) -> str | None:
        """Get the latest bundle version from S3."""
        latest_key = "bundles/latest"

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
            versions = await self.list_versions()
            return versions[0]["version"] if versions else None

    def get_bundle_key(self, version: str) -> str:
        """Get the S3 key for a bundle."""
        return f"bundles/{version}/hydra-agent-{version}.zip"


# =============================================================================
# Local Bundle Storage Service
# =============================================================================

class LocalBundleStorageService(BaseStorageService):
    """Local filesystem storage service for agent bundles."""

    def __init__(self, settings: "Settings"):
        self.base_path = Path(settings.local_storage_path)
        logger.info("initializing_local_storage", path=str(self.base_path))

        # Ensure base path exists
        if not self.base_path.exists():
            logger.warning("local_storage_path_not_found", path=str(self.base_path))

    async def get_object_stream(self, key: str) -> AsyncIterator[bytes]:
        """Stream object content from local filesystem."""
        file_path = self.base_path / key
        logger.debug("local_get_object_stream", key=key, path=str(file_path))

        if not file_path.exists():
            raise ObjectNotFoundError(key)

        try:
            chunk_size = 64 * 1024  # 64KB

            def _read_chunks():
                chunks = []
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        chunks.append(chunk)
                return chunks

            chunks = await asyncio.get_event_loop().run_in_executor(None, _read_chunks)
            for chunk in chunks:
                yield chunk

        except FileNotFoundError:
            raise ObjectNotFoundError(key)
        except PermissionError as e:
            logger.error("local_get_object_permission_denied", key=key, error=str(e))
            raise StorageUnavailableError(f"Permission denied reading file: {e}")
        except OSError as e:
            logger.error("local_get_object_failed", key=key, error=str(e), error_type="os_error")
            raise StorageUnavailableError(f"Failed to read file: {e}")
        except Exception as e:
            logger.error("local_get_object_unexpected_error", key=key, error=str(e), error_type=type(e).__name__)
            raise StorageUnavailableError(f"Failed to read file: {e}")

    async def get_object_metadata(self, key: str) -> dict:
        """Get object metadata from local filesystem."""
        file_path = self.base_path / key

        if not file_path.exists():
            raise ObjectNotFoundError(key)

        try:
            stat = file_path.stat()
            return {
                "size": stat.st_size,
                "last_modified": stat.st_mtime,
            }
        except PermissionError as e:
            logger.error("local_get_metadata_permission_denied", key=key, error=str(e))
            raise StorageUnavailableError(f"Permission denied reading metadata: {e}")
        except OSError as e:
            logger.error("local_get_metadata_failed", key=key, error=str(e), error_type="os_error")
            raise StorageUnavailableError(f"Failed to get metadata: {e}")
        except Exception as e:
            logger.error("local_get_metadata_unexpected_error", key=key, error=str(e), error_type=type(e).__name__)
            raise StorageUnavailableError(f"Failed to get metadata: {e}")

    async def list_versions(self, target: str | None = None) -> list[dict]:
        """List available bundle versions from local filesystem."""
        versions = []
        bundles_path = self.base_path

        if not bundles_path.exists():
            logger.warning("local_bundles_path_not_found", path=str(bundles_path))
            return versions

        try:
            def _list_versions():
                result = []
                for version_dir in bundles_path.iterdir():
                    if version_dir.is_dir() and version_dir.name[0].isdigit():
                        # Look for bundle zip file
                        bundle_file = version_dir / f"hydra-agent-{version_dir.name}.zip"
                        if bundle_file.exists():
                            stat = bundle_file.stat()
                            result.append({
                                "version": version_dir.name,
                                "size": stat.st_size,
                                "last_modified": stat.st_mtime,
                            })
                return result

            versions = await asyncio.get_event_loop().run_in_executor(None, _list_versions)

            # Sort by version (semantic versioning)
            versions.sort(
                key=lambda v: [
                    int(x) if x.isdigit() else 0
                    for x in v["version"].replace("-", ".").split(".")
                ],
                reverse=True,
            )

            logger.info("local_bundle_versions_found", version_count=len(versions))
            return versions[:15]

        except PermissionError as e:
            logger.error("local_list_versions_permission_denied", path=str(bundles_path), error=str(e))
            raise StorageUnavailableError(f"Permission denied listing versions: {e}")
        except OSError as e:
            logger.error("local_list_versions_failed", path=str(bundles_path), error=str(e), error_type="os_error")
            raise StorageUnavailableError(f"Failed to list local versions: {e}")
        except Exception as e:
            logger.error("local_list_versions_unexpected_error", path=str(bundles_path), error=str(e), error_type=type(e).__name__)
            raise StorageUnavailableError(f"Failed to list local versions: {e}")

    async def get_latest_version(self, target: str | None = None) -> str | None:
        """Get the latest bundle version from local filesystem."""
        latest_file = self.base_path / "latest"

        if latest_file.exists():
            try:
                content = latest_file.read_text().strip()
                if content:
                    return content
            except Exception:
                pass

        # Fall back to listing versions
        versions = await self.list_versions()
        return versions[0]["version"] if versions else None

    async def object_exists(self, key: str) -> bool:
        """Check if object exists in local filesystem."""
        file_path = self.base_path / key
        return file_path.exists()

    async def health_check(self) -> bool:
        """Check local storage availability."""
        try:
            exists = self.base_path.exists() and self.base_path.is_dir()
            logger.debug("local_health_check", path=str(self.base_path), exists=exists)
            return exists
        except Exception as e:
            logger.warning("local_health_check_failed", error=str(e))
            return False

    def get_bundle_key(self, version: str) -> str:
        """Get the local path for a bundle."""
        return f"{version}/hydra-agent-{version}.zip"


# =============================================================================
# Unified Storage Service (facade)
# =============================================================================

class StorageService:
    """Unified storage service that delegates to appropriate backend based on source.

    This is the main entry point for storage operations, providing a unified
    interface for binary downloads, S3 bundles, and local bundles.
    """

    def __init__(self, settings: "Settings"):
        self._settings = settings
        self._s3_binary: S3StorageService | None = None
        self._s3_bundle: S3BundleStorageService | None = None
        self._local_bundle: LocalBundleStorageService | None = None

        # Initialize available backends lazily
        if settings.has_object_storage:
            self._s3_binary = S3StorageService(settings)
            self._s3_bundle = S3BundleStorageService(settings)

        if settings.has_local_storage:
            self._local_bundle = LocalBundleStorageService(settings)

    def get_backend(self, source: StorageSource) -> BaseStorageService:
        """Get the appropriate storage backend for the given source."""
        if source == StorageSource.BINARY:
            if self._s3_binary is None:
                raise StorageNotConfiguredError(StorageSource.BINARY)
            return self._s3_binary
        elif source == StorageSource.OBS:
            if self._s3_bundle is None:
                raise StorageNotConfiguredError(StorageSource.OBS)
            return self._s3_bundle
        elif source == StorageSource.LOCAL:
            if self._local_bundle is None:
                raise StorageNotConfiguredError(StorageSource.LOCAL)
            return self._local_bundle
        else:
            raise InvalidStorageSourceError(source)

    def is_source_available(self, source: StorageSource) -> bool:
        """Check if a storage source is available."""
        if source == StorageSource.BINARY:
            return self._s3_binary is not None
        elif source == StorageSource.OBS:
            return self._s3_bundle is not None
        elif source == StorageSource.LOCAL:
            return self._local_bundle is not None
        return False

    def get_available_sources(self) -> list[StorageSource]:
        """Get list of available storage sources."""
        available = []
        if self._s3_binary is not None:
            available.append(StorageSource.BINARY)
        if self._s3_bundle is not None:
            available.append(StorageSource.OBS)
        if self._local_bundle is not None:
            available.append(StorageSource.LOCAL)
        return available

    # Delegate methods for backward compatibility

    async def get_object_stream(self, key: str) -> AsyncIterator[bytes]:
        """Stream object from S3 binary storage (backward compatible)."""
        if self._s3_binary is None:
            raise StorageNotConfiguredError()
        async for chunk in self._s3_binary.get_object_stream(key):
            yield chunk

    async def get_object_metadata(self, key: str) -> dict:
        """Get metadata from S3 binary storage (backward compatible)."""
        if self._s3_binary is None:
            raise StorageNotConfiguredError()
        return await self._s3_binary.get_object_metadata(key)

    async def list_versions(self, target: str) -> list[dict]:
        """List binary versions from S3 (backward compatible)."""
        if self._s3_binary is None:
            raise StorageNotConfiguredError()
        return await self._s3_binary.list_versions(target)

    async def get_latest_version(self, target: str) -> str | None:
        """Get latest binary version from S3 (backward compatible)."""
        if self._s3_binary is None:
            raise StorageNotConfiguredError()
        return await self._s3_binary.get_latest_version(target)

    async def object_exists(self, key: str) -> bool:
        """Check if object exists in S3 binary storage (backward compatible)."""
        if self._s3_binary is None:
            return False
        return await self._s3_binary.object_exists(key)

    async def health_check(self) -> dict:
        """Check health of all storage backends."""
        results = {
            "binary": None,
            "obs": None,
            "local": None,
        }

        if self._s3_binary:
            results["binary"] = await self._s3_binary.health_check()
        if self._s3_bundle:
            results["obs"] = await self._s3_bundle.health_check()
        if self._local_bundle:
            results["local"] = await self._local_bundle.health_check()

        return results


# =============================================================================
# Factory Functions
# =============================================================================

# Global instance cache
_storage_service: StorageService | None = None


def get_storage_service(settings: "Settings") -> StorageService:
    """
    Factory function to get the storage service.

    Returns the unified storage service that supports all backends.
    """
    logger.info(
        "creating_storage_service",
        has_object_storage=settings.has_object_storage,
        has_local_storage=settings.has_local_storage,
    )
    return StorageService(settings)


def get_cached_storage_service(settings: "Settings") -> StorageService | None:
    """Get or create cached storage service instance.

    Returns None if no storage backend is configured.
    """
    global _storage_service

    if not settings.has_object_storage and not settings.has_local_storage:
        logger.debug("no_storage_configured")
        return None

    if _storage_service is None:
        _storage_service = get_storage_service(settings)
    return _storage_service
