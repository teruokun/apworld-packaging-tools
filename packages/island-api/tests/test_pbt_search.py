# SPDX-License-Identifier: MIT
"""Property-based tests for search functionality.

These tests validate:
- Property 11: Search functionality preservation

Feature: registry-model-migration
"""

from datetime import datetime, timezone

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from island_api.db.models import (
    Author,
    Distribution,
    Keyword,
    Package,
    PackageEntryPoint,
    Version,
)


# =============================================================================
# Strategies for generating test data
# =============================================================================

valid_package_name = st.from_regex(r"[a-z][a-z0-9\-]{2,20}", fullmatch=True)
valid_version = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)
valid_sha256 = st.from_regex(r"[a-f0-9]{64}", fullmatch=True)
valid_platform_tag = st.sampled_from(
    ["py3-none-any", "cp311-cp311-win_amd64", "cp311-cp311-macosx_11_0_arm64"]
)
valid_file_size = st.integers(min_value=100, max_value=10_000_000)
valid_game_name = st.from_regex(r"[A-Z][a-zA-Z0-9 ]{2,30}", fullmatch=True)
valid_ap_version = st.from_regex(r"0\.[0-9]+\.[0-9]+", fullmatch=True)
valid_keyword = st.from_regex(r"[a-z]{3,10}", fullmatch=True)
valid_entry_point_name = st.from_regex(r"[A-Z][a-zA-Z0-9]{2,15}World", fullmatch=True)


# =============================================================================
# Property 11: Search functionality preservation
# Feature: registry-model-migration, Property 11: Search functionality preservation
# Validates: Requirements 7.1, 7.2, 7.3, 7.4
# =============================================================================


@pytest.mark.asyncio
class TestSearchFunctionalityPreservation:
    """Property 11: Search functionality preservation tests.

    For any search query, the registry SHALL return matching packages with
    their metadata and external URLs. Search by name, game, keywords, and
    entry points SHALL continue to function.

    **Feature: registry-model-migration, Property 11: Search functionality preservation**
    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """

    @given(
        package_name=valid_package_name,
        version=valid_version,
        game=valid_game_name,
        sha256=valid_sha256,
        size=valid_file_size,
        platform_tag=valid_platform_tag,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_by_name_returns_package_with_metadata(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        game: str,
        sha256: str,
        size: int,
        platform_tag: str,
    ):
        """Property 11: Search by name returns packages with metadata.

        For any registered package, searching by name SHALL return the package
        with its metadata. The package can then be queried for distribution
        details including external URLs.

        **Feature: registry-model-migration, Property 11: Search functionality preservation**
        **Validates: Requirements 7.1, 7.4**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description=f"Test package for {game}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version
        ver = Version(
            package_name=package_name,
            version=version,
            game=game,
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

        # Search by package name
        response = await client.get(f"/v1/island/search?q={package_name}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: package is found in search results
        package_names = [p["name"] for p in data["results"]]
        assert package_name in package_names

        # Find our package in results
        pkg_data = next(p for p in data["results"] if p["name"] == package_name)

        # Property assertion: package metadata is included
        assert pkg_data["name"] == package_name
        assert "display_name" in pkg_data
        assert "description" in pkg_data
        assert pkg_data["latest_version"] == version

        # Query version endpoint to verify external URLs are available
        version_response = await client.get(f"/v1/island/packages/{package_name}/{version}")
        assert version_response.status_code == 200

        version_data = version_response.json()

        # Property assertion: external URLs are available via version endpoint
        assert len(version_data["distributions"]) == 1
        assert version_data["distributions"][0]["external_url"] == external_url
        assert version_data["distributions"][0]["sha256"] == sha256

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        version=valid_version,
        game=valid_game_name,
        sha256=valid_sha256,
        size=valid_file_size,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_by_game_returns_matching_packages(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        game: str,
        sha256: str,
        size: int,
    ):
        """Property 11: Search by game filter returns matching packages.

        For any registered package with a specific game, filtering by game
        SHALL return that package.

        **Feature: registry-model-migration, Property 11: Search functionality preservation**
        **Validates: Requirements 7.1**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description=f"Test package for {game}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version with specific game
        ver = Version(
            package_name=package_name,
            version=version,
            game=game,
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

        # Search by game filter
        response = await client.get(f"/v1/island/search?game={game}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: package is found when filtering by game
        package_names = [p["name"] for p in data["results"]]
        assert package_name in package_names

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        version=valid_version,
        keyword=valid_keyword,
        sha256=valid_sha256,
        size=valid_file_size,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_by_keyword_returns_matching_packages(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        keyword: str,
        sha256: str,
        size: int,
    ):
        """Property 11: Search by keyword returns matching packages.

        For any registered package with a specific keyword, searching by
        that keyword SHALL return the package.

        **Feature: registry-model-migration, Property 11: Search functionality preservation**
        **Validates: Requirements 7.1**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package with keywords",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Add keyword
        kw = Keyword(package_name=package_name, keyword=keyword)
        test_session.add(kw)

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

        # Search by keyword
        response = await client.get(f"/v1/island/search?q={keyword}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: package is found when searching by keyword
        package_names = [p["name"] for p in data["results"]]
        assert package_name in package_names

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(kw)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        version=valid_version,
        entry_point_name=valid_entry_point_name,
        sha256=valid_sha256,
        size=valid_file_size,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_by_entry_point_returns_matching_packages(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        entry_point_name: str,
        sha256: str,
        size: int,
    ):
        """Property 11: Search by entry point returns matching packages.

        For any registered package with a specific entry point, filtering by
        entry point SHALL return that package with entry point information.

        **Feature: registry-model-migration, Property 11: Search functionality preservation**
        **Validates: Requirements 7.1**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package with entry points",
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

        # Add entry point
        entry_point = PackageEntryPoint(
            package_name=package_name,
            version_id=ver.id,
            entry_point_type="ap-island",
            name=entry_point_name,
            module=f"{package_name.replace('-', '_')}.world",
            attr=entry_point_name,
        )
        test_session.add(entry_point)

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

        # Search by entry point filter
        response = await client.get(f"/v1/island/search?entry_point={entry_point_name}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: package is found when filtering by entry point
        package_names = [p["name"] for p in data["results"]]
        assert package_name in package_names

        # Find our package in results
        pkg_data = next(p for p in data["results"] if p["name"] == package_name)

        # Property assertion: entry points are included in response
        assert "entry_points" in pkg_data
        ep_names = [ep["name"] for ep in pkg_data["entry_points"]]
        assert entry_point_name in ep_names

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(entry_point)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        version=valid_version,
        platform_tag=valid_platform_tag,
        sha256=valid_sha256,
        size=valid_file_size,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_by_platform_returns_matching_packages(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        platform_tag: str,
        sha256: str,
        size: int,
    ):
        """Property 11: Search by platform filter returns matching packages.

        For any registered package with a specific platform distribution,
        filtering by platform tag SHALL return that package.

        **Feature: registry-model-migration, Property 11: Search functionality preservation**
        **Validates: Requirements 7.3**
        """
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
        ver = Version(
            package_name=package_name,
            version=version,
            game="Test Game",
            pure_python=platform_tag == "py3-none-any",
            published_at=datetime.now(timezone.utc),
        )
        test_session.add(ver)
        await test_session.flush()

        # Create distribution with specific platform tag
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

        # Search by platform filter
        response = await client.get(f"/v1/island/search?platform={platform_tag}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: package is found when filtering by platform
        package_names = [p["name"] for p in data["results"]]
        assert package_name in package_names

        # Query version endpoint to verify distribution has correct platform
        version_response = await client.get(f"/v1/island/packages/{package_name}/{version}")
        assert version_response.status_code == 200

        version_data = version_response.json()

        # Property assertion: distribution has the expected platform tag
        dist_platforms = [d["platform_tag"] for d in version_data["distributions"]]
        assert platform_tag in dist_platforms

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        version=valid_version,
        min_ap_version=valid_ap_version,
        max_ap_version=valid_ap_version,
        sha256=valid_sha256,
        size=valid_file_size,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_by_ap_version_compatibility(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        min_ap_version: str,
        max_ap_version: str,
        sha256: str,
        size: int,
    ):
        """Property 11: Search by AP version compatibility returns matching packages.

        For any registered package with AP version bounds, filtering by
        compatible_with SHALL return packages compatible with that version.

        **Feature: registry-model-migration, Property 11: Search functionality preservation**
        **Validates: Requirements 7.2**
        """
        # Ensure min <= max for valid version range
        if min_ap_version > max_ap_version:
            min_ap_version, max_ap_version = max_ap_version, min_ap_version

        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package with AP version bounds",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version with AP version bounds
        ver = Version(
            package_name=package_name,
            version=version,
            game="Test Game",
            minimum_ap_version=min_ap_version,
            maximum_ap_version=max_ap_version,
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

        # Search with compatible_with filter using min_ap_version (should be compatible)
        response = await client.get(f"/v1/island/search?compatible_with={min_ap_version}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: package is found when filtering by compatible version
        package_names = [p["name"] for p in data["results"]]
        assert package_name in package_names

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        version=valid_version,
        sha256=valid_sha256,
        size=valid_file_size,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_results_include_latest_version(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        sha256: str,
        size: int,
    ):
        """Property 11: Search results include latest version information.

        For any registered package, search results SHALL include the
        latest_version field to help users identify the current version.

        **Feature: registry-model-migration, Property 11: Search functionality preservation**
        **Validates: Requirements 7.4**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package for latest version",
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

        # Search for the package
        response = await client.get(f"/v1/island/search?q={package_name}")
        assert response.status_code == 200

        data = response.json()

        # Find our package in results
        pkg_data = next((p for p in data["results"] if p["name"] == package_name), None)
        assert pkg_data is not None

        # Property assertion: latest_version is included
        assert "latest_version" in pkg_data
        assert pkg_data["latest_version"] == version

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        num_packages=st.integers(min_value=2, max_value=4),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_search_returns_all_matching_packages(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        num_packages: int,
    ):
        """Property 11: Search returns all matching packages.

        For any set of registered packages with a common search term,
        searching SHALL return all matching packages.

        **Feature: registry-model-migration, Property 11: Search functionality preservation**
        **Validates: Requirements 7.1**
        """
        common_keyword = "testgame"
        created_packages = []
        created_versions = []
        created_distributions = []
        created_keywords = []

        # Create multiple packages with common keyword
        for i in range(num_packages):
            package_name = f"search-test-pkg-{i}-{datetime.now().timestamp():.0f}"
            version = f"1.0.{i}"

            package = Package(
                name=package_name,
                display_name=f"Search Test Package {i}",
                description=f"Test package {i} for search",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            test_session.add(package)
            created_packages.append(package)

            # Add common keyword
            kw = Keyword(package_name=package_name, keyword=common_keyword)
            test_session.add(kw)
            created_keywords.append(kw)

            ver = Version(
                package_name=package_name,
                version=version,
                game=f"Test Game {i}",
                pure_python=True,
                published_at=datetime.now(timezone.utc),
            )
            test_session.add(ver)
            created_versions.append(ver)

        await test_session.flush()

        # Add distributions
        for i, ver in enumerate(created_versions):
            filename = f"search_test_pkg_{i}-{ver.version}-py3-none-any.island"
            external_url = f"https://github.com/example/search-test-pkg-{i}/releases/download/v{ver.version}/{filename}"

            dist = Distribution(
                version_id=ver.id,
                filename=filename,
                sha256=chr(ord("a") + i) * 64,
                size=1000 + i * 100,
                platform_tag="py3-none-any",
                external_url=external_url,
            )
            test_session.add(dist)
            created_distributions.append(dist)

        await test_session.commit()

        # Search by common keyword
        response = await client.get(f"/v1/island/search?q={common_keyword}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: all packages with the keyword are found
        found_names = {p["name"] for p in data["results"]}
        expected_names = {pkg.name for pkg in created_packages}
        assert expected_names.issubset(found_names)

        # Cleanup
        for dist in created_distributions:
            await test_session.delete(dist)
        for kw in created_keywords:
            await test_session.delete(kw)
        for ver in created_versions:
            await test_session.delete(ver)
        for pkg in created_packages:
            await test_session.delete(pkg)
        await test_session.commit()
