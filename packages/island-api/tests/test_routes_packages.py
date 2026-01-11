# SPDX-License-Identifier: MIT
"""Tests for package listing, search, and metadata endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_packages_empty(client: AsyncClient):
    """Test listing packages when repository is empty."""
    response = await client.get("/v1/island/packages")
    assert response.status_code == 200

    data = response.json()
    assert data["packages"] == []
    assert data["pagination"]["total"] == 0
    assert data["pagination"]["page"] == 1


@pytest.mark.asyncio
async def test_list_packages_with_data(client: AsyncClient, sample_packages):
    """Test listing packages with data."""
    response = await client.get("/v1/island/packages")
    assert response.status_code == 200

    data = response.json()
    assert len(data["packages"]) == 4
    assert data["pagination"]["total"] == 4

    # Check packages are sorted by name
    names = [p["name"] for p in data["packages"]]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_list_packages_pagination(client: AsyncClient, sample_packages):
    """Test pagination of package listing."""
    # First page
    response = await client.get("/v1/island/packages?page=1&per_page=2")
    assert response.status_code == 200

    data = response.json()
    assert len(data["packages"]) == 2
    assert data["pagination"]["total"] == 4
    assert data["pagination"]["total_pages"] == 2
    assert data["pagination"]["page"] == 1

    # Second page
    response = await client.get("/v1/island/packages?page=2&per_page=2")
    assert response.status_code == 200

    data = response.json()
    assert len(data["packages"]) == 2
    assert data["pagination"]["page"] == 2


@pytest.mark.asyncio
async def test_get_package(client: AsyncClient, sample_package):
    """Test getting package metadata."""
    response = await client.get("/v1/island/packages/pokemon-emerald")
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "pokemon-emerald"
    assert data["display_name"] == "Pokemon Emerald"
    assert data["description"] == "Pokemon Emerald randomizer for Archipelago"
    assert data["license"] == "MIT"
    assert len(data["authors"]) == 1
    assert data["authors"][0]["name"] == "Zunawe"
    assert len(data["keywords"]) == 3
    assert data["latest_version"] == "2.1.0"


@pytest.mark.asyncio
async def test_get_package_not_found(client: AsyncClient):
    """Test getting non-existent package."""
    response = await client.get("/v1/island/packages/nonexistent")
    assert response.status_code == 404

    data = response.json()
    assert data["error"]["code"] == "PACKAGE_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_versions(client: AsyncClient, sample_package):
    """Test listing package versions."""
    response = await client.get("/v1/island/packages/pokemon-emerald/versions")
    assert response.status_code == 200

    data = response.json()
    assert data["package_name"] == "pokemon-emerald"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version"] == "2.1.0"
    assert data["versions"][0]["yanked"] is False


@pytest.mark.asyncio
async def test_list_versions_not_found(client: AsyncClient):
    """Test listing versions for non-existent package."""
    response = await client.get("/v1/island/packages/nonexistent/versions")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_version(client: AsyncClient, sample_package):
    """Test getting specific version metadata."""
    response = await client.get("/v1/island/packages/pokemon-emerald/2.1.0")
    assert response.status_code == 200

    data = response.json()
    assert data["version"] == "2.1.0"
    assert data["game"] == "Pokemon Emerald"
    assert data["minimum_ap_version"] == "0.5.0"
    assert data["maximum_ap_version"] == "0.6.99"
    assert data["pure_python"] is True
    assert data["yanked"] is False


@pytest.mark.asyncio
async def test_get_version_not_found(client: AsyncClient, sample_package):
    """Test getting non-existent version."""
    response = await client.get("/v1/island/packages/pokemon-emerald/9.9.9")
    assert response.status_code == 404

    data = response.json()
    assert data["error"]["code"] == "VERSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_search_empty_query(client: AsyncClient, sample_packages):
    """Test search with empty query returns all packages."""
    response = await client.get("/v1/island/search")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 4
    assert len(data["results"]) == 4


@pytest.mark.asyncio
async def test_search_by_name(client: AsyncClient, sample_packages):
    """Test search by package name."""
    response = await client.get("/v1/island/search?q=pokemon")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["name"] == "pokemon-emerald"


@pytest.mark.asyncio
async def test_search_by_game(client: AsyncClient, sample_packages):
    """Test search filtered by game."""
    response = await client.get("/v1/island/search?game=Hollow")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["name"] == "hollow-knight"


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient, sample_packages):
    """Test search with no matching results."""
    response = await client.get("/v1/island/search?q=nonexistent")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_get_index(client: AsyncClient, sample_packages):
    """Test getting full package index."""
    response = await client.get("/v1/island/index.json")
    assert response.status_code == 200

    data = response.json()
    assert data["total_packages"] == 4
    assert data["total_versions"] == 4
    assert "generated_at" in data
    assert "pokemon-emerald" in data["packages"]
    assert "hollow-knight" in data["packages"]


@pytest.mark.asyncio
async def test_get_index_empty(client: AsyncClient):
    """Test getting index when repository is empty."""
    response = await client.get("/v1/island/index.json")
    assert response.status_code == 200

    data = response.json()
    assert data["total_packages"] == 0
    assert data["total_versions"] == 0
    assert data["packages"] == {}


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_search_by_platform(client: AsyncClient, packages_with_platforms):
    """Test search filtered by platform tag."""
    # Search for pure Python packages
    response = await client.get("/v1/island/search?platform=py3-none-any")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["name"] == "pure-python-world"
    assert data["filters"]["platform"] == "py3-none-any"


@pytest.mark.asyncio
async def test_search_by_platform_windows(client: AsyncClient, packages_with_platforms):
    """Test search filtered by Windows platform tag."""
    response = await client.get("/v1/island/search?platform=cp311-cp311-win_amd64")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["name"] == "windows-world"


@pytest.mark.asyncio
async def test_search_by_platform_no_results(client: AsyncClient, packages_with_platforms):
    """Test search with platform that has no matching packages."""
    response = await client.get("/v1/island/search?platform=cp311-cp311-linux_x86_64")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 0
    assert data["results"] == []
