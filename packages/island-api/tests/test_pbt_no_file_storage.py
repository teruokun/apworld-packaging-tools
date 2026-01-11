# SPDX-License-Identifier: MIT
"""Property-based tests for registry model - no file storage.

Property 6: No file storage
For any registered package, the registry SHALL NOT store the actual distribution files.
Only metadata, URLs, and checksums SHALL be persisted.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**
"""

from datetime import datetime, timezone

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from island_api.db.models import (
    Distribution,
    Package,
    Version,
)


# Strategies for generating valid data
valid_package_name = st.from_regex(r"[a-z][a-z0-9\-]{2,20}", fullmatch=True)
valid_version = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)
valid_sha256 = st.from_regex(r"[a-f0-9]{64}", fullmatch=True)
valid_external_url = st.from_regex(
    r"https://github\.com/[a-z]+/[a-z\-]+/releases/download/v[0-9]+\.[0-9]+\.[0-9]+/[a-z_]+\-[0-9]+\.[0-9]+\.[0-9]+\-py3\-none\-any\.island",
    fullmatch=True,
)
valid_platform_tag = st.sampled_from(
    ["py3-none-any", "cp311-cp311-win_amd64", "cp311-cp311-macosx_11_0_arm64"]
)
valid_file_size = st.integers(min_value=100, max_value=10_000_000)


@pytest.mark.asyncio
class TestNoFileStorage:
    """Property 6: No file storage tests.

    **Feature: registry-model-migration, Property 6: No file storage**
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """

    @given(
        package_name=valid_package_name,
        version=valid_version,
        sha256=valid_sha256,
        size=valid_file_size,
        platform_tag=valid_platform_tag,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_distribution_stores_external_url_not_file_path(
        self,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        sha256: str,
        size: int,
        platform_tag: str,
    ):
        """Property 6: Distribution model stores external_url, not storage_path.

        For any distribution, the model SHALL have an external_url field
        and SHALL NOT have a storage_path field.

        **Feature: registry-model-migration, Property 6: No file storage**
        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package for no file storage property",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version
        ver = Version(
            package_name=package_name,
            version=version,
            game="Test Game",
            pure_python=True,
            published_at=datetime.now(timezone.utc),
        )
        test_session.add(ver)
        await test_session.flush()

        # Create distribution with external URL
        filename = f"{package_name.replace('-', '_')}-{version}-{platform_tag}.island"
        external_url = (
            f"https://github.com/example/{package_name}/releases/download/v{version}/{filename}"
        )

        distribution = Distribution(
            version_id=ver.id,
            filename=filename,
            sha256=sha256,
            size=size,
            platform_tag=platform_tag,
            external_url=external_url,
        )
        test_session.add(distribution)
        await test_session.commit()

        # Verify distribution was stored correctly
        await test_session.refresh(distribution)

        # Property assertion: external_url is stored
        assert distribution.external_url == external_url
        assert distribution.external_url.startswith("https://")

        # Property assertion: no storage_path attribute exists
        assert not hasattr(distribution, "storage_path")

        # Property assertion: no download_count attribute exists (can't track external downloads)
        assert not hasattr(distribution, "download_count")

        # Property assertion: registered_at timestamp exists
        assert distribution.registered_at is not None

        # Property assertion: url_status for health tracking exists
        assert distribution.url_status == "active"

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        version=valid_version,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_distribution_table_schema_has_no_file_storage_columns(
        self,
        test_session: AsyncSession,
        package_name: str,
        version: str,
    ):
        """Property 6: Distribution table schema has no file storage columns.

        The distributions table SHALL NOT have columns for storing file paths
        or download counts (which would imply file hosting).

        **Feature: registry-model-migration, Property 6: No file storage**
        **Validates: Requirements 1.1, 1.2**
        """
        # Get the table columns using SQLAlchemy inspection
        mapper = inspect(Distribution)
        column_names = {column.key for column in mapper.columns}

        # Property assertion: external_url column exists
        assert "external_url" in column_names

        # Property assertion: storage_path column does NOT exist
        assert "storage_path" not in column_names

        # Property assertion: download_count column does NOT exist
        assert "download_count" not in column_names

        # Property assertion: uploaded_at column does NOT exist (replaced by registered_at)
        assert "uploaded_at" not in column_names

        # Property assertion: registered_at column exists
        assert "registered_at" in column_names

        # Property assertion: url health tracking columns exist
        assert "last_verified_at" in column_names
        assert "url_status" in column_names

    @given(
        package_name=valid_package_name,
        version=valid_version,
        sha256=valid_sha256,
        size=valid_file_size,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_distribution_stores_checksum_for_verification(
        self,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        sha256: str,
        size: int,
    ):
        """Property 6: Distribution stores checksum for client-side verification.

        For any distribution, the registry SHALL store the SHA256 checksum
        so clients can verify downloads from external URLs.

        **Feature: registry-model-migration, Property 6: No file storage**
        **Validates: Requirements 1.4**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package for checksum storage",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version
        ver = Version(
            package_name=package_name,
            version=version,
            game="Test Game",
            pure_python=True,
            published_at=datetime.now(timezone.utc),
        )
        test_session.add(ver)
        await test_session.flush()

        # Create distribution
        filename = f"{package_name.replace('-', '_')}-{version}-py3-none-any.island"
        external_url = (
            f"https://github.com/example/{package_name}/releases/download/v{version}/{filename}"
        )

        distribution = Distribution(
            version_id=ver.id,
            filename=filename,
            sha256=sha256,
            size=size,
            platform_tag="py3-none-any",
            external_url=external_url,
        )
        test_session.add(distribution)
        await test_session.commit()

        # Verify checksum is stored correctly
        await test_session.refresh(distribution)

        # Property assertion: SHA256 checksum is stored
        assert distribution.sha256 == sha256
        assert len(distribution.sha256) == 64
        assert all(c in "0123456789abcdef" for c in distribution.sha256)

        # Property assertion: size is stored for verification
        assert distribution.size == size
        assert distribution.size > 0

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        version=valid_version,
        num_distributions=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_multiple_distributions_all_use_external_urls(
        self,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        num_distributions: int,
    ):
        """Property 6: All distributions use external URLs.

        For any package with multiple distributions (different platforms),
        ALL distributions SHALL use external URLs, not file storage.

        **Feature: registry-model-migration, Property 6: No file storage**
        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        platform_tags = ["py3-none-any", "cp311-cp311-win_amd64", "cp311-cp311-macosx_11_0_arm64"]

        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package with multiple distributions",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version
        ver = Version(
            package_name=package_name,
            version=version,
            game="Test Game",
            pure_python=False,
            published_at=datetime.now(timezone.utc),
        )
        test_session.add(ver)
        await test_session.flush()

        # Create multiple distributions
        distributions = []
        for i in range(num_distributions):
            platform_tag = platform_tags[i % len(platform_tags)]
            filename = f"{package_name.replace('-', '_')}-{version}-{platform_tag}.island"
            external_url = (
                f"https://github.com/example/{package_name}/releases/download/v{version}/{filename}"
            )

            dist = Distribution(
                version_id=ver.id,
                filename=filename,
                sha256="a" * 64,
                size=1000 + i * 100,
                platform_tag=platform_tag,
                external_url=external_url,
            )
            test_session.add(dist)
            distributions.append(dist)

        await test_session.commit()

        # Verify all distributions use external URLs
        for dist in distributions:
            await test_session.refresh(dist)

            # Property assertion: each distribution has external_url
            assert dist.external_url is not None
            assert dist.external_url.startswith("https://")

            # Property assertion: no storage_path
            assert not hasattr(dist, "storage_path")

        # Cleanup
        for dist in distributions:
            await test_session.delete(dist)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()
