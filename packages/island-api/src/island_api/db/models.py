# SPDX-License-Identifier: MIT
"""SQLAlchemy database models for Island repository."""

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class Package(Base):
    """Package metadata model.

    Represents a registered Island package in the repository.
    """

    __tablename__ = "packages"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    homepage: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    repository: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)
    total_downloads: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    versions: Mapped[list["Version"]] = relationship(
        "Version", back_populates="package", cascade="all, delete-orphan"
    )
    authors: Mapped[list["Author"]] = relationship(
        "Author", back_populates="package", cascade="all, delete-orphan"
    )
    keywords: Mapped[list["Keyword"]] = relationship(
        "Keyword", back_populates="package", cascade="all, delete-orphan"
    )
    publishers: Mapped[list["Publisher"]] = relationship(
        "Publisher", back_populates="package", cascade="all, delete-orphan"
    )
    entry_points: Mapped[list["PackageEntryPoint"]] = relationship(
        "PackageEntryPoint", back_populates="package", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Package(name={self.name!r}, display_name={self.display_name!r})>"


class Version(Base):
    """Package version model.

    Represents a specific version of an Island package.
    """

    __tablename__ = "versions"
    __table_args__ = (UniqueConstraint("package_name", "version", name="uq_package_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_name: Mapped[str] = mapped_column(
        String(100), ForeignKey("packages.name", ondelete="CASCADE")
    )
    version: Mapped[str] = mapped_column(String(50))
    game: Mapped[str] = mapped_column(String(100))
    minimum_ap_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    maximum_ap_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pure_python: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    yanked: Mapped[bool] = mapped_column(Boolean, default=False)
    yank_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    package: Mapped["Package"] = relationship("Package", back_populates="versions")
    distributions: Mapped[list["Distribution"]] = relationship(
        "Distribution", back_populates="version", cascade="all, delete-orphan"
    )
    entry_points: Mapped[list["PackageEntryPoint"]] = relationship(
        "PackageEntryPoint", back_populates="version", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Version(package={self.package_name!r}, version={self.version!r})>"


class Distribution(Base):
    """Distribution reference model.

    Represents a reference to an externally-hosted distribution file.
    The registry does NOT store the actual file, only metadata and URL.
    """

    __tablename__ = "distributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(Integer, ForeignKey("versions.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))  # Expected checksum
    size: Mapped[int] = mapped_column(Integer)
    platform_tag: Mapped[str] = mapped_column(String(50))  # e.g., "py3-none-any"

    # External URL instead of storage_path (registry-only model)
    external_url: Mapped[str] = mapped_column(String(2000))  # URL to download from

    # Registration timestamp
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    # URL health tracking
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    url_status: Mapped[str] = mapped_column(String(20), default="active")  # active, unavailable

    # Relationships
    version: Mapped["Version"] = relationship("Version", back_populates="distributions")

    def __repr__(self) -> str:
        return f"<Distribution(filename={self.filename!r}, sha256={self.sha256[:8]}...)>"


class Author(Base):
    """Package author model."""

    __tablename__ = "authors"
    __table_args__ = (UniqueConstraint("package_name", "name", name="uq_package_author"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_name: Mapped[str] = mapped_column(
        String(100), ForeignKey("packages.name", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    package: Mapped["Package"] = relationship("Package", back_populates="authors")

    def __repr__(self) -> str:
        return f"<Author(name={self.name!r})>"


class Keyword(Base):
    """Package keyword model for search."""

    __tablename__ = "keywords"
    __table_args__ = (UniqueConstraint("package_name", "keyword", name="uq_package_keyword"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_name: Mapped[str] = mapped_column(
        String(100), ForeignKey("packages.name", ondelete="CASCADE")
    )
    keyword: Mapped[str] = mapped_column(String(50))

    # Relationships
    package: Mapped["Package"] = relationship("Package", back_populates="keywords")

    def __repr__(self) -> str:
        return f"<Keyword(keyword={self.keyword!r})>"


class Publisher(Base):
    """Package publisher/owner model.

    Tracks who can publish new versions of a package.
    """

    __tablename__ = "publishers"
    __table_args__ = (
        UniqueConstraint("package_name", "publisher_id", name="uq_package_publisher"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_name: Mapped[str] = mapped_column(
        String(100), ForeignKey("packages.name", ondelete="CASCADE")
    )
    publisher_id: Mapped[str] = mapped_column(String(255))  # User ID or GitHub repo
    publisher_type: Mapped[str] = mapped_column(String(20))  # "user" or "trusted_publisher"
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    # For trusted publishers (GitHub Actions OIDC)
    github_repository: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    github_workflow: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    package: Mapped["Package"] = relationship("Package", back_populates="publishers")

    def __repr__(self) -> str:
        return f"<Publisher(publisher_id={self.publisher_id!r}, type={self.publisher_type!r})>"


class AuditLog(Base):
    """Audit log for package modifications.

    Records all changes to packages for security and compliance.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_name: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(50))  # "upload", "yank", "add_publisher", etc.
    actor_id: Mapped[str] = mapped_column(String(255))
    actor_type: Mapped[str] = mapped_column(String(20))  # "user" or "trusted_publisher"
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, index=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON details

    # Provenance for trusted publishers
    github_repository: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    github_workflow: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    github_commit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog(action={self.action!r}, package={self.package_name!r})>"


class APIToken(Base):
    """API token for authentication.

    Stores hashed API tokens for user authentication during uploads.
    """

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Token description
    scopes: Mapped[str] = mapped_column(String(255), default="upload")  # Comma-separated scopes
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<APIToken(user_id={self.user_id!r}, name={self.name!r})>"


class PackageEntryPoint(Base):
    """Package entry point model.

    Stores ap-island entry points extracted from uploaded packages
    for search and discovery.
    """

    __tablename__ = "package_entry_points"
    __table_args__ = (
        UniqueConstraint("package_name", "entry_point_type", "name", name="uq_package_entry_point"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_name: Mapped[str] = mapped_column(
        String(100), ForeignKey("packages.name", ondelete="CASCADE"), index=True
    )
    version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("versions.id", ondelete="CASCADE"), index=True
    )
    entry_point_type: Mapped[str] = mapped_column(String(50))  # "ap-island"
    name: Mapped[str] = mapped_column(String(100), index=True)  # Entry point name
    module: Mapped[str] = mapped_column(String(255))  # Module path
    attr: Mapped[str] = mapped_column(String(100))  # Attribute name

    # Relationships
    package: Mapped["Package"] = relationship("Package", back_populates="entry_points")
    version: Mapped["Version"] = relationship("Version", back_populates="entry_points")

    def __repr__(self) -> str:
        return f"<PackageEntryPoint(name={self.name!r}, module={self.module!r}:{self.attr!r})>"
