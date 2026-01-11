# SPDX-License-Identifier: MIT
"""Pytest fixtures for API tests."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from island_api import APIConfig, create_app
from island_api.db import get_session
from island_api.db.models import Author, Base, Distribution, Keyword, Package, Version


@pytest.fixture
def test_config() -> APIConfig:
    """Create test configuration with in-memory SQLite."""
    config = APIConfig()
    config.database.url = "sqlite+aiosqlite:///:memory:"
    config.database.echo = False
    config.rate_limit.enabled = False
    config.storage.backend = "local"
    config.storage.local_path = "/tmp/test_packages"
    return config


@pytest_asyncio.fixture
async def test_engine(test_config: APIConfig):
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
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def app(test_config: APIConfig, test_engine):
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
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def sample_package(test_session: AsyncSession) -> Package:
    """Create a sample package for testing."""
    package = Package(
        name="pokemon-emerald",
        display_name="Pokemon Emerald",
        description="Pokemon Emerald randomizer for Archipelago",
        license="MIT",
        homepage="https://github.com/ArchipelagoMW/Archipelago",
        repository="https://github.com/ArchipelagoMW/Archipelago",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        total_downloads=100,
    )
    test_session.add(package)

    # Add authors
    author = Author(
        package_name="pokemon-emerald",
        name="Zunawe",
        email="zunawe@example.com",
    )
    test_session.add(author)

    # Add keywords
    for kw in ["pokemon", "gba", "emerald"]:
        keyword = Keyword(package_name="pokemon-emerald", keyword=kw)
        test_session.add(keyword)

    # Add version
    version = Version(
        package_name="pokemon-emerald",
        version="2.1.0",
        game="Pokemon Emerald",
        minimum_ap_version="0.5.0",
        maximum_ap_version="0.6.99",
        pure_python=True,
        published_at=datetime.now(timezone.utc),
        yanked=False,
    )
    test_session.add(version)

    await test_session.commit()
    await test_session.refresh(package)
    return package


@pytest_asyncio.fixture
async def sample_packages(test_session: AsyncSession) -> list[Package]:
    """Create multiple sample packages for testing."""
    packages = []

    for i, (name, display, game) in enumerate(
        [
            ("pokemon-emerald", "Pokemon Emerald", "Pokemon Emerald"),
            ("hollow-knight", "Hollow Knight", "Hollow Knight"),
            ("celeste", "Celeste", "Celeste"),
            ("stardew-valley", "Stardew Valley", "Stardew Valley"),
        ]
    ):
        package = Package(
            name=name,
            display_name=display,
            description=f"{display} randomizer for Archipelago",
            license="MIT",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            total_downloads=100 * (i + 1),
        )
        test_session.add(package)

        # Add version
        version = Version(
            package_name=name,
            version="1.0.0",
            game=game,
            pure_python=True,
            published_at=datetime.now(timezone.utc),
            yanked=False,
        )
        test_session.add(version)

        packages.append(package)

    await test_session.commit()
    return packages


@pytest_asyncio.fixture
async def sample_package_with_platforms(test_session: AsyncSession) -> Package:
    """Create a sample package with multiple platform-specific distributions."""
    package = Package(
        name="native-world",
        display_name="Native World",
        description="A world with native code requiring platform-specific builds",
        license="MIT",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        total_downloads=50,
    )
    test_session.add(package)

    # Add version
    version = Version(
        package_name="native-world",
        version="1.0.0",
        game="Native Game",
        pure_python=False,
        published_at=datetime.now(timezone.utc),
        yanked=False,
    )
    test_session.add(version)
    await test_session.flush()

    # Add multiple platform-specific distributions
    distributions = [
        Distribution(
            version_id=version.id,
            filename="native_world-1.0.0-py3-none-any.island",
            sha256="a" * 64,
            size=1000,
            platform_tag="py3-none-any",
            external_url="https://github.com/example/native-world/releases/download/v1.0.0/native_world-1.0.0-py3-none-any.island",
        ),
        Distribution(
            version_id=version.id,
            filename="native_world-1.0.0-cp311-cp311-win_amd64.island",
            sha256="b" * 64,
            size=2000,
            platform_tag="cp311-cp311-win_amd64",
            external_url="https://github.com/example/native-world/releases/download/v1.0.0/native_world-1.0.0-cp311-cp311-win_amd64.island",
        ),
        Distribution(
            version_id=version.id,
            filename="native_world-1.0.0-cp311-cp311-macosx_11_0_arm64.island",
            sha256="c" * 64,
            size=1800,
            platform_tag="cp311-cp311-macosx_11_0_arm64",
            external_url="https://github.com/example/native-world/releases/download/v1.0.0/native_world-1.0.0-cp311-cp311-macosx_11_0_arm64.island",
        ),
    ]
    for dist in distributions:
        test_session.add(dist)

    await test_session.commit()
    await test_session.refresh(package)
    return package


@pytest_asyncio.fixture
async def packages_with_platforms(test_session: AsyncSession) -> list[Package]:
    """Create packages with different platform distributions for search testing."""
    packages = []

    # Package 1: Pure Python only
    pkg1 = Package(
        name="pure-python-world",
        display_name="Pure Python World",
        description="A pure Python world",
        license="MIT",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_session.add(pkg1)

    ver1 = Version(
        package_name="pure-python-world",
        version="1.0.0",
        game="Pure Game",
        pure_python=True,
        published_at=datetime.now(timezone.utc),
    )
    test_session.add(ver1)
    await test_session.flush()

    dist1 = Distribution(
        version_id=ver1.id,
        filename="pure_python_world-1.0.0-py3-none-any.island",
        sha256="d" * 64,
        size=500,
        platform_tag="py3-none-any",
        external_url="https://github.com/example/pure-python-world/releases/download/v1.0.0/pure_python_world-1.0.0-py3-none-any.island",
    )
    test_session.add(dist1)
    packages.append(pkg1)

    # Package 2: Windows only
    pkg2 = Package(
        name="windows-world",
        display_name="Windows World",
        description="A Windows-only world",
        license="MIT",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_session.add(pkg2)

    ver2 = Version(
        package_name="windows-world",
        version="1.0.0",
        game="Windows Game",
        pure_python=False,
        published_at=datetime.now(timezone.utc),
    )
    test_session.add(ver2)
    await test_session.flush()

    dist2 = Distribution(
        version_id=ver2.id,
        filename="windows_world-1.0.0-cp311-cp311-win_amd64.island",
        sha256="e" * 64,
        size=1500,
        platform_tag="cp311-cp311-win_amd64",
        external_url="https://github.com/example/windows-world/releases/download/v1.0.0/windows_world-1.0.0-cp311-cp311-win_amd64.island",
    )
    test_session.add(dist2)
    packages.append(pkg2)

    await test_session.commit()
    return packages
