# SPDX-License-Identifier: MIT
"""Integration test: End-to-end publish flow.

Tests the complete flow of:
1. Building an .apworld from a sample project
2. Starting a test API server
3. Publishing the .apworld to the server
4. Downloading and verifying the package
"""

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apworld_api import APIConfig, create_app
from apworld_api.auth.tokens import generate_api_token, hash_token
from apworld_api.db import get_session
from apworld_api.db.models import APIToken, Base
from apworld_build.apworld import build_apworld
from apworld_build.config import BuildConfig


class TestEndToEndPublishFlow:
    """Integration tests for the complete publish flow."""

    @pytest.fixture
    def sample_project_dir(self) -> Path:
        """Get the sample project directory."""
        return Path(__file__).parent / "sample_apworld"

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
    async def test_build_publish_download_flow(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
        client: AsyncClient,
        api_token: str,
    ):
        """Test the complete build -> publish -> download flow."""
        # Step 1: Build the .apworld
        config = BuildConfig(
            name="sample-game",
            version="1.0.0",
            game_name="Sample Game",
            source_dir=sample_source_dir,
            description="A sample APWorld for testing",
            authors=["Test Author"],
            minimum_ap_version="0.5.0",
        )

        build_result = build_apworld(config, output_dir=tmp_path)
        assert build_result.path.exists()

        # Read the built file
        with open(build_result.path, "rb") as f:
            apworld_content = f.read()

        # Compute checksum
        checksum = self._compute_sha256(apworld_content)

        # Step 2: Upload to the API server
        files = {"file": (build_result.filename, apworld_content, "application/octet-stream")}
        headers = {
            "Authorization": f"Bearer {api_token}",
        }

        response = await client.post(
            "/v1/packages/sample-game/upload",
            files=files,
            headers=headers,
            params={"sha256": checksum},
        )

        assert response.status_code == 200, f"Upload failed: {response.text}"
        upload_data = response.json()
        assert upload_data["package"] == "sample-game"
        assert upload_data["version"] == "1.0.0"
        assert upload_data["sha256"] == checksum

        # Step 3: Verify the package is listed
        response = await client.get("/v1/packages/sample-game")
        assert response.status_code == 200
        package_data = response.json()
        assert package_data["name"] == "sample-game"
        assert package_data["display_name"] == "Sample Game"

        # Step 4: Verify the version is listed
        response = await client.get("/v1/packages/sample-game/versions")
        assert response.status_code == 200
        versions_data = response.json()
        assert len(versions_data["versions"]) == 1
        assert versions_data["versions"][0]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_publish_and_verify_metadata(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
        client: AsyncClient,
        api_token: str,
    ):
        """Test that published package metadata is correctly stored."""
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

        build_result = build_apworld(config, output_dir=tmp_path)

        with open(build_result.path, "rb") as f:
            apworld_content = f.read()

        checksum = self._compute_sha256(apworld_content)

        # Upload
        files = {"file": (build_result.filename, apworld_content, "application/octet-stream")}
        headers = {"Authorization": f"Bearer {api_token}"}

        response = await client.post(
            "/v1/packages/metadata-test/upload",
            files=files,
            headers=headers,
            params={"sha256": checksum},
        )
        assert response.status_code == 200

        # Verify metadata
        response = await client.get("/v1/packages/metadata-test")
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
        """Test that uploading the same version twice fails."""
        config = BuildConfig(
            name="immutable-test",
            version="1.0.0",
            game_name="Immutable Test",
            source_dir=sample_source_dir,
        )

        build_result = build_apworld(config, output_dir=tmp_path)

        with open(build_result.path, "rb") as f:
            apworld_content = f.read()

        checksum = self._compute_sha256(apworld_content)
        files = {"file": (build_result.filename, apworld_content, "application/octet-stream")}
        headers = {"Authorization": f"Bearer {api_token}"}

        # First upload should succeed
        response = await client.post(
            "/v1/packages/immutable-test/upload",
            files=files,
            headers=headers,
            params={"sha256": checksum},
        )
        assert response.status_code == 200

        # Second upload of same version should fail
        response = await client.post(
            "/v1/packages/immutable-test/upload",
            files=files,
            headers=headers,
            params={"sha256": checksum},
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
        """Test that checksum mismatch is rejected."""
        config = BuildConfig(
            name="checksum-test",
            version="1.0.0",
            game_name="Checksum Test",
            source_dir=sample_source_dir,
        )

        build_result = build_apworld(config, output_dir=tmp_path)

        with open(build_result.path, "rb") as f:
            apworld_content = f.read()

        # Provide wrong checksum
        wrong_checksum = "0" * 64
        files = {"file": (build_result.filename, apworld_content, "application/octet-stream")}
        headers = {"Authorization": f"Bearer {api_token}"}

        response = await client.post(
            "/v1/packages/checksum-test/upload",
            files=files,
            headers=headers,
            params={"sha256": wrong_checksum},
        )
        assert response.status_code == 400  # Bad request - checksum mismatch

    @pytest.mark.asyncio
    async def test_authentication_required(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
        client: AsyncClient,
    ):
        """Test that upload requires authentication."""
        config = BuildConfig(
            name="auth-test",
            version="1.0.0",
            game_name="Auth Test",
            source_dir=sample_source_dir,
        )

        build_result = build_apworld(config, output_dir=tmp_path)

        with open(build_result.path, "rb") as f:
            apworld_content = f.read()

        files = {"file": (build_result.filename, apworld_content, "application/octet-stream")}

        # No auth header
        response = await client.post(
            "/v1/packages/auth-test/upload",
            files=files,
        )
        assert response.status_code == 401  # Unauthorized

    @pytest.mark.asyncio
    async def test_search_published_package(
        self,
        sample_source_dir: Path,
        tmp_path: Path,
        client: AsyncClient,
        api_token: str,
    ):
        """Test that published packages appear in search results."""
        config = BuildConfig(
            name="search-test",
            version="1.0.0",
            game_name="Searchable Game",
            source_dir=sample_source_dir,
            description="A game that should be searchable",
            keywords=["searchable", "test"],
        )

        build_result = build_apworld(config, output_dir=tmp_path)

        with open(build_result.path, "rb") as f:
            apworld_content = f.read()

        checksum = self._compute_sha256(apworld_content)
        files = {"file": (build_result.filename, apworld_content, "application/octet-stream")}
        headers = {"Authorization": f"Bearer {api_token}"}

        # Upload
        response = await client.post(
            "/v1/packages/search-test/upload",
            files=files,
            headers=headers,
            params={"sha256": checksum},
        )
        assert response.status_code == 200

        # Search by name - search response uses "results" not "packages"
        response = await client.get("/v1/search", params={"q": "search-test"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) >= 1
        assert any(p["name"] == "search-test" for p in data["results"])
