# SPDX-License-Identifier: MIT
"""Property-based tests for package metadata responses.

These tests validate:
- Property 5: External URL in responses
- Property 10: Metadata completeness
- Property 12: Index completeness

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
valid_description = st.text(
    min_size=10, max_size=200, alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"))
)
valid_author_name = st.from_regex(r"[A-Z][a-z]{2,15}", fullmatch=True)
valid_keyword = st.from_regex(r"[a-z]{3,10}", fullmatch=True)


# =============================================================================
# Property 5: External URL in responses
# Feature: registry-model-migration, Property 5: External URL in responses
# Validates: Requirements 1.5, 5.1
# =============================================================================


@pytest.mark.asyncio
class TestExternalURLInResponses:
    """Property 5: External URL in responses tests.

    For any package metadata request, the registry SHALL return external URLs
    (not registry-hosted URLs) for all distributions. The response SHALL
    include the expected SHA256 checksum for each distribution.

    **Feature: registry-model-migration, Property 5: External URL in responses**
    **Validates: Requirements 1.5, 5.1**
    """

    @given(
        package_name=valid_package_name,
        version=valid_version,
        sha256=valid_sha256,
        size=valid_file_size,
        platform_tag=valid_platform_tag,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_version_endpoint_returns_external_url(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        sha256: str,
        size: int,
        platform_tag: str,
    ):
        """Property 5: GET /packages/{name}/{version} returns external URLs.

        For any registered package version, the response SHALL include
        external_url (not download_url) for each distribution.

        **Feature: registry-model-migration, Property 5: External URL in responses**
        **Validates: Requirements 1.5, 5.1**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package for external URL response",
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

        # Query the version endpoint
        response = await client.get(f"/v1/island/packages/{package_name}/{version}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: distributions are present
        assert "distributions" in data
        assert len(data["distributions"]) == 1

        dist_data = data["distributions"][0]

        # Property assertion: external_url is returned (not download_url)
        assert "external_url" in dist_data
        assert dist_data["external_url"] == external_url
        assert dist_data["external_url"].startswith("https://")

        # Property assertion: download_url is NOT returned
        assert "download_url" not in dist_data

        # Property assertion: SHA256 checksum is included
        assert "sha256" in dist_data
        assert dist_data["sha256"] == sha256

        # Property assertion: url_status is included
        assert "url_status" in dist_data
        assert dist_data["url_status"] == "active"

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
    async def test_all_distributions_have_external_urls(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        num_distributions: int,
    ):
        """Property 5: All distributions in response have external URLs.

        For any package with multiple distributions, ALL distributions
        SHALL have external_url in the response.

        **Feature: registry-model-migration, Property 5: External URL in responses**
        **Validates: Requirements 1.5, 5.1**
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
                sha256=chr(ord("a") + i) * 64,
                size=1000 + i * 100,
                platform_tag=platform_tag,
                external_url=external_url,
            )
            test_session.add(dist)
            distributions.append(dist)

        await test_session.commit()

        # Query the version endpoint
        response = await client.get(f"/v1/island/packages/{package_name}/{version}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: all distributions are returned
        assert len(data["distributions"]) == num_distributions

        # Property assertion: each distribution has external_url and sha256
        for dist_data in data["distributions"]:
            assert "external_url" in dist_data
            assert dist_data["external_url"].startswith("https://")
            assert "sha256" in dist_data
            assert len(dist_data["sha256"]) == 64
            assert "download_url" not in dist_data

        # Cleanup
        for dist in distributions:
            await test_session.delete(dist)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()


# =============================================================================
# Property 10: Metadata completeness
# Feature: registry-model-migration, Property 10: Metadata completeness
# Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
# =============================================================================


@pytest.mark.asyncio
class TestMetadataCompleteness:
    """Property 10: Metadata completeness tests.

    For any registered package, the registry SHALL store and return complete
    metadata including name, version, game, entry points, and all distribution
    URLs with checksums.

    **Feature: registry-model-migration, Property 10: Metadata completeness**
    **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
    """

    @given(
        package_name=valid_package_name,
        version=valid_version,
        game=valid_game_name,
        min_ap_version=valid_ap_version,
        max_ap_version=valid_ap_version,
        sha256=valid_sha256,
        size=valid_file_size,
        platform_tag=valid_platform_tag,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_version_metadata_complete(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        game: str,
        min_ap_version: str,
        max_ap_version: str,
        sha256: str,
        size: int,
        platform_tag: str,
    ):
        """Property 10: Version endpoint returns complete metadata.

        For any registered package version, the response SHALL include
        all required metadata fields.

        **Feature: registry-model-migration, Property 10: Metadata completeness**
        **Validates: Requirements 6.1, 6.3, 6.4, 6.5**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package for metadata completeness",
            license="MIT",
            homepage=f"https://github.com/example/{package_name}",
            repository=f"https://github.com/example/{package_name}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version with all metadata
        ver = Version(
            package_name=package_name,
            version=version,
            game=game,
            minimum_ap_version=min_ap_version,
            maximum_ap_version=max_ap_version,
            pure_python=True,
            published_at=datetime.now(timezone.utc),
        )
        test_session.add(ver)
        await test_session.flush()

        # Create distribution
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

        # Query the version endpoint
        response = await client.get(f"/v1/island/packages/{package_name}/{version}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: version metadata is complete (Req 6.1)
        assert data["version"] == version
        assert data["game"] == game

        # Property assertion: AP version compatibility bounds (Req 6.3)
        assert data["minimum_ap_version"] == min_ap_version
        assert data["maximum_ap_version"] == max_ap_version

        # Property assertion: platform tags for distributions (Req 6.4)
        assert len(data["distributions"]) == 1
        assert data["distributions"][0]["platform_tag"] == platform_tag

        # Property assertion: external URL and checksum (Req 6.5)
        assert data["distributions"][0]["external_url"] == external_url
        assert data["distributions"][0]["sha256"] == sha256
        assert data["distributions"][0]["size"] == size

        # Property assertion: publication timestamp
        assert "published_at" in data

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        version=valid_version,
        author_name=valid_author_name,
        keyword=valid_keyword,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_package_metadata_includes_authors_and_keywords(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        author_name: str,
        keyword: str,
    ):
        """Property 10: Package endpoint returns authors and keywords.

        For any registered package, the response SHALL include
        authors and keywords for search and discovery.

        **Feature: registry-model-migration, Property 10: Metadata completeness**
        **Validates: Requirements 6.1**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package with authors and keywords",
            license="MIT",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Add author
        author = Author(
            package_name=package_name,
            name=author_name,
            email=f"{author_name.lower()}@example.com",
        )
        test_session.add(author)

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
        await test_session.commit()

        # Query the package endpoint
        response = await client.get(f"/v1/island/packages/{package_name}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: package name and display name
        assert data["name"] == package_name
        assert "display_name" in data

        # Property assertion: authors are included
        assert "authors" in data
        assert len(data["authors"]) >= 1
        author_names = [a["name"] for a in data["authors"]]
        assert author_name in author_names

        # Property assertion: keywords are included
        assert "keywords" in data
        assert keyword in data["keywords"]

        # Property assertion: description is included
        assert "description" in data

        # Cleanup
        await test_session.delete(kw)
        await test_session.delete(author)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        version=valid_version,
        entry_point_name=st.from_regex(r"[A-Z][a-zA-Z0-9]{2,15}World", fullmatch=True),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_entry_points_stored_for_discovery(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        entry_point_name: str,
    ):
        """Property 10: Entry points are stored for WebWorld discovery.

        For any registered package, the registry SHALL store entry point
        declarations for WebWorld discovery.

        **Feature: registry-model-migration, Property 10: Metadata completeness**
        **Validates: Requirements 6.2**
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
        await test_session.commit()

        # Query the search endpoint with entry_point filter
        response = await client.get(f"/v1/island/search?entry_point={entry_point_name}")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: package is found by entry point
        package_names = [p["name"] for p in data["results"]]
        assert package_name in package_names

        # Find our package in results
        pkg_data = next(p for p in data["results"] if p["name"] == package_name)

        # Property assertion: entry points are included in response
        assert "entry_points" in pkg_data
        ep_names = [ep["name"] for ep in pkg_data["entry_points"]]
        assert entry_point_name in ep_names

        # Cleanup
        await test_session.delete(entry_point)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()


# =============================================================================
# Property 12: Index completeness
# Feature: registry-model-migration, Property 12: Index completeness
# Validates: Requirements 7.5
# =============================================================================


@pytest.mark.asyncio
class TestIndexCompleteness:
    """Property 12: Index completeness tests.

    For any request to the index endpoint, the registry SHALL return all
    packages with their metadata and external URLs, suitable for offline tooling.

    **Feature: registry-model-migration, Property 12: Index completeness**
    **Validates: Requirements 7.5**
    """

    @given(
        package_name=valid_package_name,
        version=valid_version,
        sha256=valid_sha256,
        size=valid_file_size,
        platform_tag=valid_platform_tag,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_index_includes_external_urls(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        version: str,
        sha256: str,
        size: int,
        platform_tag: str,
    ):
        """Property 12: Index endpoint includes external URLs for all distributions.

        For any registered package, the index SHALL include external URLs
        and checksums for all distributions.

        **Feature: registry-model-migration, Property 12: Index completeness**
        **Validates: Requirements 7.5**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package for index completeness",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        # Create version
        ver = Version(
            package_name=package_name,
            version=version,
            game="Test Game",
            minimum_ap_version="0.5.0",
            maximum_ap_version="0.6.99",
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
            url_status="active",
        )
        test_session.add(distribution)
        await test_session.commit()

        # Query the index endpoint
        response = await client.get("/v1/island/index.json")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: package is in index
        assert package_name in data["packages"]

        pkg_data = data["packages"][package_name]

        # Property assertion: version is in package
        assert version in pkg_data["versions"]

        ver_data = pkg_data["versions"][version]

        # Property assertion: distributions are included
        assert "distributions" in ver_data
        assert len(ver_data["distributions"]) == 1

        dist_data = ver_data["distributions"][0]

        # Property assertion: external_url is included (not download_url)
        assert "external_url" in dist_data
        assert dist_data["external_url"] == external_url
        assert dist_data["external_url"].startswith("https://")

        # Property assertion: checksum is included
        assert "sha256" in dist_data
        assert dist_data["sha256"] == sha256

        # Property assertion: url_status is included
        assert "url_status" in dist_data
        assert dist_data["url_status"] == "active"

        # Property assertion: size is included
        assert "size" in dist_data
        assert dist_data["size"] == size

        # Property assertion: platform_tag is included
        assert "platform_tag" in dist_data
        assert dist_data["platform_tag"] == platform_tag

        # Cleanup
        await test_session.delete(distribution)
        await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()

    @given(
        num_packages=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_index_contains_all_packages(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        num_packages: int,
    ):
        """Property 12: Index contains all registered packages.

        For any set of registered packages, the index SHALL contain
        all of them with their metadata and external URLs.

        **Feature: registry-model-migration, Property 12: Index completeness**
        **Validates: Requirements 7.5**
        """
        created_packages = []
        created_versions = []
        created_distributions = []

        # Create multiple packages
        for i in range(num_packages):
            package_name = f"test-pkg-{i}-{datetime.now().timestamp():.0f}"
            version = f"1.0.{i}"

            package = Package(
                name=package_name,
                display_name=f"Test Package {i}",
                description=f"Test package {i} for index completeness",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            test_session.add(package)
            created_packages.append(package)

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
            filename = f"test_pkg_{i}-{ver.version}-py3-none-any.island"
            external_url = f"https://github.com/example/test-pkg-{i}/releases/download/v{ver.version}/{filename}"

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

        # Query the index endpoint
        response = await client.get("/v1/island/index.json")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: all packages are in index
        for pkg in created_packages:
            assert pkg.name in data["packages"]

            pkg_data = data["packages"][pkg.name]

            # Property assertion: versions have distributions with external URLs
            for ver_str, ver_data in pkg_data["versions"].items():
                assert "distributions" in ver_data
                for dist_data in ver_data["distributions"]:
                    assert "external_url" in dist_data
                    assert dist_data["external_url"].startswith("https://")
                    assert "sha256" in dist_data

        # Property assertion: total counts are correct
        assert data["total_packages"] >= num_packages
        assert data["total_versions"] >= num_packages

        # Cleanup
        for dist in created_distributions:
            await test_session.delete(dist)
        for ver in created_versions:
            await test_session.delete(ver)
        for pkg in created_packages:
            await test_session.delete(pkg)
        await test_session.commit()

    @given(
        package_name=valid_package_name,
        num_versions=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_index_includes_all_versions(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        package_name: str,
        num_versions: int,
    ):
        """Property 12: Index includes all versions of each package.

        For any package with multiple versions, the index SHALL include
        all versions with their external URLs.

        **Feature: registry-model-migration, Property 12: Index completeness**
        **Validates: Requirements 7.5**
        """
        # Create package
        package = Package(
            name=package_name,
            display_name=package_name.replace("-", " ").title(),
            description="Test package with multiple versions",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        test_session.add(package)

        created_versions = []
        created_distributions = []

        # Create multiple versions
        for i in range(num_versions):
            version = f"1.{i}.0"

            ver = Version(
                package_name=package_name,
                version=version,
                game="Test Game",
                pure_python=True,
                published_at=datetime.now(timezone.utc),
            )
            test_session.add(ver)
            created_versions.append(ver)

        await test_session.flush()

        # Add distributions for each version
        for i, ver in enumerate(created_versions):
            filename = f"{package_name.replace('-', '_')}-{ver.version}-py3-none-any.island"
            external_url = f"https://github.com/example/{package_name}/releases/download/v{ver.version}/{filename}"

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

        # Query the index endpoint
        response = await client.get("/v1/island/index.json")
        assert response.status_code == 200

        data = response.json()

        # Property assertion: package is in index
        assert package_name in data["packages"]

        pkg_data = data["packages"][package_name]

        # Property assertion: all versions are included
        assert len(pkg_data["versions"]) == num_versions

        for ver in created_versions:
            assert ver.version in pkg_data["versions"]

            ver_data = pkg_data["versions"][ver.version]

            # Property assertion: each version has distributions with external URLs
            assert "distributions" in ver_data
            assert len(ver_data["distributions"]) >= 1

            for dist_data in ver_data["distributions"]:
                assert "external_url" in dist_data
                assert "sha256" in dist_data

        # Cleanup
        for dist in created_distributions:
            await test_session.delete(dist)
        for ver in created_versions:
            await test_session.delete(ver)
        await test_session.delete(package)
        await test_session.commit()
