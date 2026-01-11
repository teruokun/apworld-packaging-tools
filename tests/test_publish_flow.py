# SPDX-License-Identifier: MIT
"""Integration test: End-to-end registration flow.

Tests the complete flow of:
1. Building an .island from a sample project
2. Starting a test API server
3. Registering the .island with external URLs
4. Querying and verifying the package metadata

Note: This test file has been updated for the registry-only model.
The upload endpoint has been replaced with the registration endpoint.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from island_api import APIConfig, create_app
from island_api.auth.tokens import generate_api_token
from island_api.db import get_session
from island_api.db.models import APIToken, Base
from island_build.island import build_island
from island_build.config import BuildConfig


def create_mock_response(content: bytes, status_code: int = 200) -> MagicMock:
    """Create a mock httpx Response that works with raise_for_status."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = status_code
    mock_response.content = content
    mock_response.headers = {"content-length": str(len(content))}
    mock_response.is_success = 200 <= status_code < 300

    # Make raise_for_status work correctly
    def raise_for_status():
        if not mock_response.is_success:
            raise httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=mock_response,
            )

    mock_response.raise_for_status = raise_for_status
    return mock_response


class TestEndToEndPublishFlow:
    """Integration tests for the complete registration flow."""

    @pytest.fixture
    def sample_project_dir(self) -> Path:
        """Get the sample project directory."""
        return Path(__file__).parent / "sample_island"

    @pytest.fixture
    def sample_source_dir(self, sample_project_dir: Path) -> Path:
        """Get the sample source directory."""
        return sample_project_dir / "src" / "sample_game"

    @pytest.fixture
    def test_config(self, tmp_path: Path) -> APIConfig:
        """Create test configuration with in-memory SQLite."""
        config = APIConfig()
        config.database.url = "sqlite+aiosqlite:///:memory:"
        config.database.echo = False
        config.rate_limit.enabled = False
        config.storage.backend = "local"
        config.storage.local_path = str(tmp_path / "packages")
        return config

    @pytest_asyncio.fixture
    async def test_engine(self, test_config: APIConfig):
        """Create test database engine."""
        engine = create_async_engine(
            test_config.database.url,
            echo=test_config.database.echo,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()

    @pytest_asyncio.fixture
    async def test_session(self, test_engine) -> AsyncSession:
        """Create test database session."""
        session_factory = async_sessionmaker(
            test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            yield session

    @pytest_asyncio.fixture
    async def app(self, test_config: APIConfig, test_engine):
        """Create test FastAPI application."""
        app = create_app(test_config)

        # Override database session dependency
        session_factory = async_sessionmaker(
            test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async def override_get_session():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        return app

    @pytest_asyncio.fixture
    async def client(self, app) -> AsyncClient:
        """Create test HTTP client."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

    @pytest_asyncio.fixture
    async def api_token(self, test_session: AsyncSession) -> str:
        """Create an API token for testing."""
        token, token_hash = generate_api_token()

        db_token = APIToken(
            token_hash=token_hash,
            user_id="test-user",
            name="Test Token",
            scopes="upload",
            created_at=datetime.now(timezone.utc),
        )
        test_session.add(db_token)
        await test_session.commit()

        return token

    def _compute_sha256(self, data: bytes) -> str:
        """Compute SHA256 hash of data."""
        return hashlib.sha256(data).hexdigest()

    @pytest.mark.asyncio
    async def test_build_register_query_flow(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
        client: AsyncClient,
        api_token: str,
    ):
        """Test the complete build -> register -> query flow."""
        # Step 1: Build the .island
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
            description="A sample Island for testing",
            authors=["Test Author"],
            minimum_ap_version="0.5.0",
        )

        build_result = build_island(config, output_dir=tmp_path)
        assert build_result.path.exists()

        # Read the built file
        with open(build_result.path, "rb") as f:
            island_content = f.read()

        # Compute checksum
        checksum = self._compute_sha256(island_content)
        size = len(island_content)

        # Step 2: Register with the API server (mock external URL verification)
        external_url = (
            f"https://github.com/test/sample-game/releases/download/v1.0.0/{build_result.filename}"
        )

        registration_payload = {
            "name": "sample-game",
            "version": "1.0.0",
            "game": "Sample Game",
            "description": "A sample Island for testing",
            "authors": ["Test Author"],
            "minimum_ap_version": "0.5.0",
            "entry_points": {"sample_game": "sample_game:SampleWorld"},
            "distributions": [
                {
                    "filename": build_result.filename,
                    "url": external_url,
                    "sha256": checksum,
                    "size": size,
                    "platform_tag": "py3-none-any",
                }
            ],
        }

        headers = {"Authorization": f"Bearer {api_token}"}

        # Mock the external URL verification
        with patch("island_api.routes.register.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock HEAD request (URL accessibility check)
            mock_client.head.return_value = create_mock_response(b"", 200)

            # Mock GET request (download for checksum verification)
            mock_client.get.return_value = create_mock_response(island_content, 200)

            response = await client.post(
                "/v1/island/register",
                json=registration_payload,
                headers=headers,
            )

        assert response.status_code == 200, f"Registration failed: {response.text}"
        register_data = response.json()
        assert register_data["package_name"] == "sample-game"
        assert register_data["version"] == "1.0.0"

        # Step 3: Verify the package is listed
        response = await client.get("/v1/island/packages/sample-game")
        assert response.status_code == 200
        package_data = response.json()
        assert package_data["name"] == "sample-game"
        assert package_data["display_name"] == "Sample Game"

        # Step 4: Verify the version is listed
        response = await client.get("/v1/island/packages/sample-game/versions")
        assert response.status_code == 200
        versions_data = response.json()
        assert len(versions_data["versions"]) == 1
        assert versions_data["versions"][0]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_register_and_verify_metadata(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
        client: AsyncClient,
        api_token: str,
    ):
        """Test that registered package metadata is correctly stored."""
        # Build with full metadata
        config = BuildConfig(
            name="metadata-test",
            version="2.0.0",
            game_name="Metadata Test Game",
            source_dir=sample_source_dir,
            description="Testing metadata preservation",
            authors=["Author One", "Author Two"],
            minimum_ap_version="0.5.0",
            maximum_ap_version="0.6.99",
            license="MIT",
            keywords=["test", "metadata"],
        )

        build_result = build_island(config, output_dir=tmp_path)

        with open(build_result.path, "rb") as f:
            island_content = f.read()

        checksum = self._compute_sha256(island_content)
        size = len(island_content)
        external_url = f"https://github.com/test/metadata-test/releases/download/v2.0.0/{build_result.filename}"

        registration_payload = {
            "name": "metadata-test",
            "version": "2.0.0",
            "game": "Metadata Test Game",
            "description": "Testing metadata preservation",
            "authors": ["Author One", "Author Two"],
            "minimum_ap_version": "0.5.0",
            "maximum_ap_version": "0.6.99",
            "license": "MIT",
            "keywords": ["test", "metadata"],
            "entry_points": {"metadata_test": "metadata_test:MetadataWorld"},
            "distributions": [
                {
                    "filename": build_result.filename,
                    "url": external_url,
                    "sha256": checksum,
                    "size": size,
                    "platform_tag": "py3-none-any",
                }
            ],
        }

        headers = {"Authorization": f"Bearer {api_token}"}

        # Mock the external URL verification
        with patch("island_api.routes.register.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.head.return_value = create_mock_response(b"", 200)
            mock_client.get.return_value = create_mock_response(island_content, 200)

            response = await client.post(
                "/v1/island/register",
                json=registration_payload,
                headers=headers,
            )

        assert response.status_code == 200, f"Registration failed: {response.text}"

        # Verify metadata
        response = await client.get("/v1/island/packages/metadata-test")
        assert response.status_code == 200
        data = response.json()

        assert data["display_name"] == "Metadata Test Game"
        assert data["description"] == "Testing metadata preservation"
        # Authors are returned as objects with name and email fields
        author_names = [a["name"] for a in data["authors"]]
        assert "Author One" in author_names
        assert "Author Two" in author_names

    @pytest.mark.asyncio
    async def test_version_immutability(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
        client: AsyncClient,
        api_token: str,
    ):
        """Test that registering the same version twice fails."""
        config = BuildConfig(
            name="immutable-test",
            version="1.0.0",
            game_name="Immutable Test",
            source_dir=sample_source_dir,
        )

        build_result = build_island(config, output_dir=tmp_path)

        with open(build_result.path, "rb") as f:
            island_content = f.read()

        checksum = self._compute_sha256(island_content)
        size = len(island_content)
        external_url = f"https://github.com/test/immutable-test/releases/download/v1.0.0/{build_result.filename}"

        registration_payload = {
            "name": "immutable-test",
            "version": "1.0.0",
            "game": "Immutable Test",
            "description": "Test package",
            "authors": ["Test Author"],
            "minimum_ap_version": "0.5.0",
            "entry_points": {"immutable_test": "immutable_test:ImmutableWorld"},
            "distributions": [
                {
                    "filename": build_result.filename,
                    "url": external_url,
                    "sha256": checksum,
                    "size": size,
                    "platform_tag": "py3-none-any",
                }
            ],
        }

        headers = {"Authorization": f"Bearer {api_token}"}

        # Mock the external URL verification
        with patch("island_api.routes.register.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.head.return_value = create_mock_response(b"", 200)
            mock_client.get.return_value = create_mock_response(island_content, 200)

            # First registration should succeed
            response = await client.post(
                "/v1/island/register",
                json=registration_payload,
                headers=headers,
            )
            assert response.status_code == 200

            # Second registration of same version should fail
            response = await client.post(
                "/v1/island/register",
                json=registration_payload,
                headers=headers,
            )
            assert response.status_code == 409  # Conflict - version exists

    @pytest.mark.asyncio
    async def test_checksum_verification(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
        client: AsyncClient,
        api_token: str,
    ):
        """Test that checksum mismatch is rejected during registration."""
        config = BuildConfig(
            name="checksum-test",
            version="1.0.0",
            game_name="Checksum Test",
            source_dir=sample_source_dir,
        )

        build_result = build_island(config, output_dir=tmp_path)

        with open(build_result.path, "rb") as f:
            island_content = f.read()

        # Provide wrong checksum
        wrong_checksum = "0" * 64
        size = len(island_content)
        external_url = f"https://github.com/test/checksum-test/releases/download/v1.0.0/{build_result.filename}"

        registration_payload = {
            "name": "checksum-test",
            "version": "1.0.0",
            "game": "Checksum Test",
            "description": "Test package",
            "authors": ["Test Author"],
            "minimum_ap_version": "0.5.0",
            "entry_points": {"checksum_test": "checksum_test:ChecksumWorld"},
            "distributions": [
                {
                    "filename": build_result.filename,
                    "url": external_url,
                    "sha256": wrong_checksum,  # Wrong checksum
                    "size": size,
                    "platform_tag": "py3-none-any",
                }
            ],
        }

        headers = {"Authorization": f"Bearer {api_token}"}

        # Mock the external URL verification - returns actual content
        with patch("island_api.routes.register.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.head.return_value = create_mock_response(b"", 200)
            mock_client.get.return_value = create_mock_response(island_content, 200)

            response = await client.post(
                "/v1/island/register",
                json=registration_payload,
                headers=headers,
            )

        assert response.status_code == 400  # Bad request - checksum mismatch

    @pytest.mark.asyncio
    async def test_authentication_required(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
        client: AsyncClient,
    ):
        """Test that registration requires authentication."""
        config = BuildConfig(
            name="auth-test",
            version="1.0.0",
            game_name="Auth Test",
            source_dir=sample_source_dir,
        )

        build_result = build_island(config, output_dir=tmp_path)

        with open(build_result.path, "rb") as f:
            island_content = f.read()

        checksum = self._compute_sha256(island_content)
        size = len(island_content)
        external_url = (
            f"https://github.com/test/auth-test/releases/download/v1.0.0/{build_result.filename}"
        )

        registration_payload = {
            "name": "auth-test",
            "version": "1.0.0",
            "game": "Auth Test",
            "description": "Test package",
            "authors": ["Test Author"],
            "minimum_ap_version": "0.5.0",
            "entry_points": {"auth_test": "auth_test:AuthWorld"},
            "distributions": [
                {
                    "filename": build_result.filename,
                    "url": external_url,
                    "sha256": checksum,
                    "size": size,
                    "platform_tag": "py3-none-any",
                }
            ],
        }

        # No auth header
        response = await client.post(
            "/v1/island/register",
            json=registration_payload,
        )
        assert response.status_code == 401  # Unauthorized

    @pytest.mark.asyncio
    async def test_search_registered_package(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
        client: AsyncClient,
        api_token: str,
    ):
        """Test that registered packages appear in search results."""
        config = BuildConfig(
            name="search-test",
            version="1.0.0",
            game_name="Searchable Game",
            source_dir=sample_source_dir,
            description="A game that should be searchable",
            keywords=["searchable", "test"],
        )

        build_result = build_island(config, output_dir=tmp_path)

        with open(build_result.path, "rb") as f:
            island_content = f.read()

        checksum = self._compute_sha256(island_content)
        size = len(island_content)
        external_url = (
            f"https://github.com/test/search-test/releases/download/v1.0.0/{build_result.filename}"
        )

        registration_payload = {
            "name": "search-test",
            "version": "1.0.0",
            "game": "Searchable Game",
            "description": "A game that should be searchable",
            "authors": ["Test Author"],
            "minimum_ap_version": "0.5.0",
            "keywords": ["searchable", "test"],
            "entry_points": {"search_test": "search_test:SearchWorld"},
            "distributions": [
                {
                    "filename": build_result.filename,
                    "url": external_url,
                    "sha256": checksum,
                    "size": size,
                    "platform_tag": "py3-none-any",
                }
            ],
        }

        headers = {"Authorization": f"Bearer {api_token}"}

        # Mock the external URL verification
        with patch("island_api.routes.register.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.head.return_value = create_mock_response(b"", 200)
            mock_client.get.return_value = create_mock_response(island_content, 200)

            response = await client.post(
                "/v1/island/register",
                json=registration_payload,
                headers=headers,
            )

        assert response.status_code == 200, f"Registration failed: {response.text}"

        # Search by name - search response uses "results" not "packages"
        response = await client.get("/v1/island/search", params={"q": "search-test"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) >= 1
        assert any(p["name"] == "search-test" for p in data["results"])
