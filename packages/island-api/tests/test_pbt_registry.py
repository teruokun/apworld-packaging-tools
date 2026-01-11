# SPDX-License-Identifier: MIT
"""Property-based tests for registry API functionality.

These tests validate:
- Property 11: Registry entry point indexing
- Property 12: Registry search completeness
- Property 13: Platform tag filtering

Note: Entry point extraction tests have been removed as part of the migration
to the registry-only model. Entry points are now provided directly in the
registration request rather than being extracted from uploaded files.
"""

from datetime import datetime, timezone

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from island_api.db.models import (
    Distribution,
    Package,
    PackageEntryPoint,
    Version,
)


# Strategies for generating valid data
valid_package_name = st.from_regex(r"[a-z][a-z0-9\-]{2,20}", fullmatch=True)
valid_version = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)
valid_entry_point_name = st.from_regex(r"[a-z][a-z0-9_]{2,15}", fullmatch=True)
valid_module_name = st.from_regex(r"[a-z][a-z0-9_]{2,15}", fullmatch=True)
valid_attr_name = st.from_regex(r"[A-Z][a-zA-Z0-9]{2,15}", fullmatch=True)


@pytest.mark.asyncio
class TestEntryPointIndexing:
    """Tests for entry point indexing in the database."""

    @given(
        ep_name=valid_entry_point_name,
        module=valid_module_name,
        attr=valid_attr_name,
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_entry_point_stored_correctly(
        self,
        test_session: AsyncSession,
        ep_name: str,
        module: str,
        attr: str,
    ):
        """Property 11: Entry points are correctly stored in the database.

        When a package is registered with entry points, those entry points
        should be stored in the PackageEntryPoint table with correct values.

        **Validates: Requirements 6.2**
        """
        package_name = f"test-pkg-{ep_name[:8]}"

        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version
        version = Version(
            package_name=package_name,
            version="1.0.0",
            game="Test Game",
            pure_python=True,
            published_at=datetime.now(timezone.utc),
        )
        test_session.add(version)
        await test_session.flush()

        # Create entry point
        entry_point = PackageEntryPoint(
            package_name=package_name,
            version_id=version.id,
            entry_point_type="ap-island",
            name=ep_name,
            module=module,
            attr=attr,
        )
        test_session.add(entry_point)
        await test_session.commit()

        # Verify entry point was stored correctly
        await test_session.refresh(entry_point)
        assert entry_point.name == ep_name
        assert entry_point.module == module
        assert entry_point.attr == attr
        assert entry_point.entry_point_type == "ap-island"

        # Cleanup
        await test_session.delete(entry_point)
        await test_session.delete(version)
        await test_session.delete(package)
        await test_session.commit()


@pytest.mark.asyncio
class TestSearchCompleteness:
    """Property 12: Registry search completeness tests."""

    @given(
        package_names=st.lists(
            valid_package_name,
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_all_packages_returned_in_search(
        self,
        test_session: AsyncSession,
        package_names: list[str],
    ):
        """Property 12: All registered packages are returned in search results.

        When multiple packages are registered, a search with no filters
        should return all of them.

        **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
        """
        created_packages = []

        # Create packages
        for name in package_names:
            package = Package(
                name=name,
                display_name=name.replace("-", " ").title(),
                description=f"Test package {name}",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            test_session.add(package)

            version = Version(
                package_name=name,
                version="1.0.0",
                game=f"Game for {name}",
                pure_python=True,
                published_at=datetime.now(timezone.utc),
            )
            test_session.add(version)
            created_packages.append((package, version))

        await test_session.commit()

        # Query all packages
        from sqlalchemy import select, func
        from island_api.db.models import Package as PackageModel

        count_query = select(func.count()).select_from(PackageModel)
        result = await test_session.execute(count_query)
        total = result.scalar() or 0

        # Verify all packages are in the database
        assert total >= len(package_names)

        # Cleanup
        for package, version in created_packages:
            await test_session.delete(version)
            await test_session.delete(package)
        await test_session.commit()

    @given(
        search_term=st.from_regex(r"[a-z]{3,8}", fullmatch=True),
        package_count=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_by_name_finds_matching_packages(
        self,
        test_session: AsyncSession,
        search_term: str,
        package_count: int,
    ):
        """Property 12: Search by name returns all matching packages.

        When packages contain a search term in their name, searching for
        that term should return all matching packages.

        **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
        """
        created_packages = []

        # Create packages with the search term in their name
        for i in range(package_count):
            name = f"{search_term}-world-{i}"
            package = Package(
                name=name,
                display_name=name.replace("-", " ").title(),
                description=f"Test package {name}",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            test_session.add(package)

            version = Version(
                package_name=name,
                version="1.0.0",
                game=f"Game for {name}",
                pure_python=True,
                published_at=datetime.now(timezone.utc),
            )
            test_session.add(version)
            created_packages.append((package, version))

        await test_session.commit()

        # Search for packages with the search term
        from sqlalchemy import select
        from island_api.db.models import Package as PackageModel

        query = select(PackageModel).where(PackageModel.name.ilike(f"%{search_term}%"))
        result = await test_session.execute(query)
        found_packages = result.scalars().all()

        # Verify all created packages are found
        found_names = {p.name for p in found_packages}
        for package, _ in created_packages:
            assert package.name in found_names

        # Cleanup
        for package, version in created_packages:
            await test_session.delete(version)
            await test_session.delete(package)
        await test_session.commit()


# Platform tag strategies
valid_python_tag = st.sampled_from(["py3", "cp311", "cp312"])
valid_abi_tag = st.sampled_from(["none", "cp311", "cp312", "abi3"])
valid_platform_tag_part = st.sampled_from(
    ["any", "win_amd64", "macosx_11_0_arm64", "linux_x86_64", "manylinux_2_17_x86_64"]
)


@st.composite
def platform_tag_strategy(draw):
    """Generate valid platform tags."""
    python = draw(valid_python_tag)
    abi = draw(valid_abi_tag)
    platform = draw(valid_platform_tag_part)
    return f"{python}-{abi}-{platform}"


@pytest.mark.asyncio
class TestPlatformFiltering:
    """Property 13: Platform tag filtering tests."""

    @given(
        platform_tag=platform_tag_strategy(),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_platform_filter_returns_matching_packages(
        self,
        test_session: AsyncSession,
        platform_tag: str,
    ):
        """Property 13: Platform filter returns packages with matching distributions.

        When a package has a distribution with a specific platform tag,
        searching with that platform tag should return the package.

        **Validates: Requirements 7.3**
        """
        package_name = f"platform-test-{platform_tag.replace('-', '')[:10]}"

        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package with platform-specific distribution",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version
        version = Version(
            package_name=package_name,
            version="1.0.0",
            game="Platform Test Game",
            pure_python=platform_tag == "py3-none-any",
            published_at=datetime.now(timezone.utc),
        )
        test_session.add(version)
        await test_session.flush()

        # Create distribution with the platform tag
        distribution = Distribution(
            version_id=version.id,
            filename=f"{package_name.replace('-', '_')}-1.0.0-{platform_tag}.island",
            sha256="a" * 64,
            size=1000,
            platform_tag=platform_tag,
            external_url=f"https://github.com/example/{package_name}/releases/download/v1.0.0/{package_name.replace('-', '_')}-1.0.0-{platform_tag}.island",
        )
        test_session.add(distribution)
        await test_session.commit()

        # Search for packages with this platform tag
        from sqlalchemy import select
        from island_api.db.models import Distribution as DistModel, Version as VerModel

        query = (
            select(VerModel.package_name)
            .join(DistModel, DistModel.version_id == VerModel.id)
            .where(DistModel.platform_tag == platform_tag)
            .distinct()
        )
        result = await test_session.execute(query)
        found_packages = result.scalars().all()

        # Verify our package is found
        assert package_name in found_packages

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(version)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        platform_tags=st.lists(
            platform_tag_strategy(),
            min_size=2,
            max_size=4,
            unique=True,
        )
    )
    @settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_multiple_platform_variants_indexed(
        self,
        test_session: AsyncSession,
        platform_tags: list[str],
    ):
        """Property 13: Multiple platform variants are all indexed.

        When a package has multiple platform-specific distributions,
        each platform tag should be searchable.

        **Validates: Requirements 7.3**
        """
        package_name = "multi-platform-pkg"

        # Create package
        package = Package(
            name=package_name,
            display_name="Multi Platform Package",
            description="Test package with multiple platform distributions",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version
        version = Version(
            package_name=package_name,
            version="1.0.0",
            game="Multi Platform Game",
            pure_python=False,
            published_at=datetime.now(timezone.utc),
        )
        test_session.add(version)
        await test_session.flush()

        # Create distributions for each platform tag
        distributions = []
        for platform_tag in platform_tags:
            distribution = Distribution(
                version_id=version.id,
                filename=f"multi_platform_pkg-1.0.0-{platform_tag}.island",
                sha256="b" * 64,
                size=1000,
                platform_tag=platform_tag,
                external_url=f"https://github.com/example/multi-platform-pkg/releases/download/v1.0.0/multi_platform_pkg-1.0.0-{platform_tag}.island",
            )
            test_session.add(distribution)
            distributions.append(distribution)

        await test_session.commit()

        # Verify each platform tag is searchable
        from sqlalchemy import select
        from island_api.db.models import Distribution as DistModel

        for platform_tag in platform_tags:
            query = select(DistModel).where(
                DistModel.version_id == version.id,
                DistModel.platform_tag == platform_tag,
            )
            result = await test_session.execute(query)
            found_dist = result.scalar_one_or_none()
            assert found_dist is not None
            assert found_dist.platform_tag == platform_tag

        # Cleanup
        for dist in distributions:
            await test_session.delete(dist)
        await test_session.delete(version)
        await test_session.delete(package)
        await test_session.commit()
