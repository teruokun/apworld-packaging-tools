# SPDX-License-Identifier: MIT
"""Wheel metadata generation for Island packages.

This module implements PEP 427 compliant wheel metadata generation:
- WHEEL file: Wheel format metadata
- METADATA file: Package metadata (PEP 566)
- RECORD file: File manifest with checksums
- entry_points.txt: Entry point declarations

References:
- PEP 427: https://peps.python.org/pep-0427/
- PEP 566: https://peps.python.org/pep-0566/
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .filename import PlatformTag


# Generator identifier for WHEEL file
GENERATOR = "island-build"
WHEEL_VERSION = "1.0"


@dataclass
class WheelMetadata:
    """PEP 427 WHEEL file metadata.

    Attributes:
        wheel_version: Wheel format version (default: "1.0")
        generator: Tool that generated the wheel
        root_is_purelib: Whether the package is pure Python
        tags: List of platform compatibility tags
    """

    wheel_version: str = WHEEL_VERSION
    generator: str = GENERATOR
    root_is_purelib: bool = True
    tags: list[str] = field(default_factory=list)

    def to_string(self) -> str:
        """Generate WHEEL file content.

        Returns:
            WHEEL file content as string

        Examples:
            >>> meta = WheelMetadata(tags=["py3-none-any"])
            >>> print(meta.to_string())
            Wheel-Version: 1.0
            Generator: island-build
            Root-Is-Purelib: true
            Tag: py3-none-any
        """
        lines = [
            f"Wheel-Version: {self.wheel_version}",
            f"Generator: {self.generator}",
            f"Root-Is-Purelib: {'true' if self.root_is_purelib else 'false'}",
        ]
        for tag in self.tags:
            lines.append(f"Tag: {tag}")
        return "\n".join(lines) + "\n"

    @classmethod
    def from_platform_tag(
        cls,
        platform_tag: "PlatformTag",
        generator: str | None = None,
    ) -> "WheelMetadata":
        """Create WheelMetadata from a PlatformTag.

        Args:
            platform_tag: Platform compatibility tag
            generator: Optional generator name (defaults to GENERATOR)

        Returns:
            WheelMetadata instance
        """
        from .filename import is_pure_python_tag

        tag_str = str(platform_tag)
        return cls(
            generator=generator or GENERATOR,
            root_is_purelib=is_pure_python_tag(platform_tag),
            tags=[tag_str],
        )


@dataclass
class PackageMetadata:
    """PEP 566 METADATA file content.

    This represents the core package metadata that goes into the METADATA file.
    Note: Island packages do NOT include Requires-Dist for runtime dependencies
    since all dependencies are vendored.

    Attributes:
        metadata_version: Metadata format version (default: "2.1")
        name: Package name
        version: Package version
        summary: Short description
        author: Author name(s)
        author_email: Author email(s)
        license: License identifier
        keywords: Package keywords
        home_page: Homepage URL
        project_url: Additional project URLs
        description: Long description
        description_content_type: Content type of description
    """

    name: str
    version: str
    metadata_version: str = "2.1"
    summary: str = ""
    author: str = ""
    author_email: str = ""
    license: str = ""
    keywords: list[str] = field(default_factory=list)
    home_page: str = ""
    project_urls: dict[str, str] = field(default_factory=dict)
    description: str = ""
    description_content_type: str = "text/plain"

    def to_string(self) -> str:
        """Generate METADATA file content.

        Returns:
            METADATA file content as string (PEP 566 compliant)

        Examples:
            >>> meta = PackageMetadata(name="my-game", version="1.0.0", summary="A game")
            >>> content = meta.to_string()
            >>> "Metadata-Version: 2.1" in content
            True
            >>> "Name: my-game" in content
            True
        """
        lines = [
            f"Metadata-Version: {self.metadata_version}",
            f"Name: {self.name}",
            f"Version: {self.version}",
        ]

        if self.summary:
            lines.append(f"Summary: {self.summary}")

        if self.author:
            lines.append(f"Author: {self.author}")

        if self.author_email:
            lines.append(f"Author-email: {self.author_email}")

        if self.license:
            lines.append(f"License: {self.license}")

        if self.keywords:
            lines.append(f"Keywords: {','.join(self.keywords)}")

        if self.home_page:
            lines.append(f"Home-page: {self.home_page}")

        for label, url in self.project_urls.items():
            lines.append(f"Project-URL: {label}, {url}")

        # Note: We intentionally do NOT include Requires-Dist
        # Island packages vendor all dependencies

        # Add description at the end with blank line separator
        if self.description:
            lines.append(f"Description-Content-Type: {self.description_content_type}")
            lines.append("")
            lines.append(self.description)

        return "\n".join(lines) + "\n"

    @classmethod
    def from_build_config(cls, config: "BuildConfig") -> "PackageMetadata":
        """Create PackageMetadata from a BuildConfig.

        Args:
            config: Build configuration

        Returns:
            PackageMetadata instance
        """
        from .config import BuildConfig

        # Format authors
        author = ", ".join(config.authors) if config.authors else ""

        # Build project URLs
        project_urls: dict[str, str] = {}
        if config.homepage:
            project_urls["Homepage"] = config.homepage
        if config.repository:
            project_urls["Repository"] = config.repository

        return cls(
            name=config.name,
            version=config.version,
            summary=config.description,
            author=author,
            license=config.license,
            keywords=config.keywords,
            home_page=config.homepage,
            project_urls=project_urls,
            description=config.description,
        )


if TYPE_CHECKING:
    from .config import BuildConfig


@dataclass
class RecordEntry:
    """A single entry in the RECORD file.

    Attributes:
        path: File path relative to the archive root
        hash_digest: Base64-encoded SHA256 hash (or empty for RECORD itself)
        size: File size in bytes (or empty for RECORD itself)
    """

    path: str
    hash_digest: str = ""
    size: int | None = None

    def to_string(self) -> str:
        """Generate RECORD entry line.

        Returns:
            CSV-formatted RECORD entry

        Examples:
            >>> entry = RecordEntry("my_game/__init__.py", "sha256=abc123", 42)
            >>> entry.to_string()
            'my_game/__init__.py,sha256=abc123,42'

            >>> entry = RecordEntry("my_game-1.0.0.dist-info/RECORD")
            >>> entry.to_string()
            'my_game-1.0.0.dist-info/RECORD,,'
        """
        size_str = str(self.size) if self.size is not None else ""
        return f"{self.path},{self.hash_digest},{size_str}"


def compute_file_hash(file_path: Path) -> tuple[str, int]:
    """Compute SHA256 hash and size of a file.

    Args:
        file_path: Path to the file

    Returns:
        Tuple of (base64-encoded hash with sha256= prefix, file size)

    Examples:
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(delete=False) as f:
        ...     _ = f.write(b"hello world")
        ...     path = Path(f.name)
        >>> hash_str, size = compute_file_hash(path)
        >>> hash_str.startswith("sha256=")
        True
        >>> size
        11
    """
    sha256 = hashlib.sha256()
    size = 0

    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
            size += len(chunk)

    # Base64 encode without padding (urlsafe)
    digest = base64.urlsafe_b64encode(sha256.digest()).rstrip(b"=").decode("ascii")
    return f"sha256={digest}", size


def compute_content_hash(content: bytes) -> tuple[str, int]:
    """Compute SHA256 hash and size of content bytes.

    Args:
        content: Content bytes

    Returns:
        Tuple of (base64-encoded hash with sha256= prefix, content size)

    Examples:
        >>> hash_str, size = compute_content_hash(b"hello world")
        >>> hash_str.startswith("sha256=")
        True
        >>> size
        11
    """
    sha256 = hashlib.sha256(content)
    digest = base64.urlsafe_b64encode(sha256.digest()).rstrip(b"=").decode("ascii")
    return f"sha256={digest}", len(content)


@dataclass
class RecordFile:
    """PEP 427 RECORD file containing file manifest with checksums.

    The RECORD file lists all files in the wheel with their SHA256 checksums
    and sizes. The RECORD file itself is listed without a hash.

    Attributes:
        entries: List of record entries
        record_path: Path to the RECORD file itself (added without hash)
    """

    entries: list[RecordEntry] = field(default_factory=list)
    record_path: str = ""

    def add_file(self, path: str, file_path: Path) -> None:
        """Add a file entry by computing its hash.

        Args:
            path: Path as it appears in the archive
            file_path: Actual file path to read and hash
        """
        hash_digest, size = compute_file_hash(file_path)
        self.entries.append(RecordEntry(path=path, hash_digest=hash_digest, size=size))

    def add_content(self, path: str, content: bytes) -> None:
        """Add an entry for content that will be written to the archive.

        Args:
            path: Path as it appears in the archive
            content: Content bytes
        """
        hash_digest, size = compute_content_hash(content)
        self.entries.append(RecordEntry(path=path, hash_digest=hash_digest, size=size))

    def to_string(self) -> str:
        """Generate RECORD file content.

        Returns:
            RECORD file content as CSV

        Examples:
            >>> record = RecordFile(record_path="my_game-1.0.0.dist-info/RECORD")
            >>> record.add_content("my_game/__init__.py", b"# init")
            >>> content = record.to_string()
            >>> "my_game/__init__.py,sha256=" in content
            True
            >>> "RECORD,," in content
            True
        """
        lines = [entry.to_string() for entry in self.entries]
        # Add RECORD itself without hash
        if self.record_path:
            lines.append(f"{self.record_path},,")
        return "\n".join(lines) + "\n"


@dataclass
class EntryPointsFile:
    """Entry points file in INI format.

    Entry points are organized by group (e.g., "ap-island", "console_scripts").
    For Island packages, the primary group is "ap-island" which declares
    WebWorld implementations.

    Attributes:
        groups: Dictionary mapping group names to entry point dictionaries
    """

    groups: dict[str, dict[str, str]] = field(default_factory=dict)

    def add_entry_point(self, group: str, name: str, value: str) -> None:
        """Add an entry point to a group.

        Args:
            group: Entry point group (e.g., "ap-island")
            name: Entry point name
            value: Entry point value (e.g., "my_game.world:MyGameWorld")

        Examples:
            >>> ep = EntryPointsFile()
            >>> ep.add_entry_point("ap-island", "my_game", "my_game.world:MyGameWorld")
            >>> "ap-island" in ep.groups
            True
        """
        if group not in self.groups:
            self.groups[group] = {}
        self.groups[group][name] = value

    def to_string(self) -> str:
        """Generate entry_points.txt content in INI format.

        Returns:
            Entry points file content

        Examples:
            >>> ep = EntryPointsFile()
            >>> ep.add_entry_point("ap-island", "my_game", "my_game.world:MyGameWorld")
            >>> content = ep.to_string()
            >>> "[ap-island]" in content
            True
            >>> "my_game = my_game.world:MyGameWorld" in content
            True
        """
        if not self.groups:
            return ""

        lines: list[str] = []
        for group_name, entries in sorted(self.groups.items()):
            lines.append(f"[{group_name}]")
            for name, value in sorted(entries.items()):
                lines.append(f"{name} = {value}")
            lines.append("")  # Blank line between groups

        return "\n".join(lines)

    @classmethod
    def from_pyproject_dict(cls, pyproject: dict) -> "EntryPointsFile":
        """Create EntryPointsFile from pyproject.toml entry-points section.

        Args:
            pyproject: Parsed pyproject.toml dictionary

        Returns:
            EntryPointsFile instance

        Examples:
            >>> pyproject = {
            ...     "project": {
            ...         "entry-points": {
            ...             "ap-island": {"my_game": "my_game.world:MyGameWorld"}
            ...         }
            ...     }
            ... }
            >>> ep = EntryPointsFile.from_pyproject_dict(pyproject)
            >>> ep.groups["ap-island"]["my_game"]
            'my_game.world:MyGameWorld'
        """
        entry_points = pyproject.get("project", {}).get("entry-points", {})
        instance = cls()
        for group, entries in entry_points.items():
            for name, value in entries.items():
                instance.add_entry_point(group, name, value)
        return instance

    def has_ap_island_entry_points(self) -> bool:
        """Check if there are any ap-island entry points.

        Returns:
            True if at least one ap-island entry point exists
        """
        return bool(self.groups.get("ap-island"))


def get_dist_info_name(name: str, version: str) -> str:
    """Get the dist-info directory name for a package.

    Args:
        name: Package name (will be normalized)
        version: Package version

    Returns:
        dist-info directory name (e.g., "my_game-1.0.0.dist-info")

    Examples:
        >>> get_dist_info_name("my-game", "1.0.0")
        'my_game-1.0.0.dist-info'
    """
    from .filename import normalize_name, normalize_version

    norm_name = normalize_name(name)
    norm_version = normalize_version(version)
    return f"{norm_name}-{norm_version}.dist-info"
