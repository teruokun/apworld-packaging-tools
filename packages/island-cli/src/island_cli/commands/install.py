# SPDX-License-Identifier: MIT
"""Install Island packages from the Package Index."""

from __future__ import annotations

import hashlib
from pathlib import Path

import click
import httpx

from ..main import Context, echo_error, echo_info, echo_success, echo_warning, pass_context


DEFAULT_REPOSITORY = "https://islands.archipelago.gg/v1"


class ChecksumMismatchError(Exception):
    """Raised when downloaded content checksum doesn't match expected value."""

    def __init__(self, expected: str, actual: str, url: str) -> None:
        self.expected = expected
        self.actual = actual
        self.url = url
        super().__init__(
            f"Checksum verification failed!\n"
            f"Expected: {expected}\n"
            f"Got: {actual}\n"
            f"URL: {url}\n"
            f"The file may have been tampered with or corrupted."
        )


def _compute_sha256(content: bytes) -> str:
    """Compute SHA256 hash of content.

    Args:
        content: Bytes to hash

    Returns:
        SHA256 hash as lowercase hex string (64 characters)
    """
    return hashlib.sha256(content).hexdigest()


def download_and_verify(
    url: str,
    expected_sha256: str,
    output_path: Path,
    timeout: float = 300.0,
) -> int:
    """Download from external URL and verify checksum.

    Downloads the file from the external URL (following redirects),
    computes the SHA256 checksum, and verifies it matches the expected
    value from the registry.

    Args:
        url: External URL to download from
        expected_sha256: Expected SHA256 checksum (64 lowercase hex chars)
        output_path: Path to write the downloaded file
        timeout: Request timeout in seconds

    Returns:
        Size of downloaded content in bytes

    Raises:
        ChecksumMismatchError: If computed checksum doesn't match expected
        httpx.HTTPError: If download fails
    """
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()

        content = response.content

        # Compute checksum
        actual_sha256 = _compute_sha256(content)

        # Verify checksum
        if actual_sha256 != expected_sha256.lower():
            raise ChecksumMismatchError(
                expected=expected_sha256.lower(),
                actual=actual_sha256,
                url=url,
            )

        # Write to output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)

        return len(content)


async def download_and_verify_async(
    url: str,
    expected_sha256: str,
    output_path: Path,
    timeout: float = 300.0,
) -> int:
    """Async version of download_and_verify.

    Downloads the file from the external URL (following redirects),
    computes the SHA256 checksum, and verifies it matches the expected
    value from the registry.

    Args:
        url: External URL to download from
        expected_sha256: Expected SHA256 checksum (64 lowercase hex chars)
        output_path: Path to write the downloaded file
        timeout: Request timeout in seconds

    Returns:
        Size of downloaded content in bytes

    Raises:
        ChecksumMismatchError: If computed checksum doesn't match expected
        httpx.HTTPError: If download fails
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()

        content = response.content

        # Compute checksum
        actual_sha256 = _compute_sha256(content)

        # Verify checksum
        if actual_sha256 != expected_sha256.lower():
            raise ChecksumMismatchError(
                expected=expected_sha256.lower(),
                actual=actual_sha256,
                url=url,
            )

        # Write to output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)

        return len(content)


def _get_package_metadata(
    repository: str,
    package_name: str,
    version: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """Fetch package metadata from the registry.

    Args:
        repository: Registry base URL
        package_name: Name of the package
        version: Specific version (or None for latest)
        timeout: Request timeout in seconds

    Returns:
        Package/version metadata dict

    Raises:
        httpx.HTTPError: If request fails
    """
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        if version:
            url = f"{repository.rstrip('/')}/packages/{package_name}/{version}"
        else:
            # Get package info to find latest version
            url = f"{repository.rstrip('/')}/packages/{package_name}"

        response = client.get(url)
        response.raise_for_status()
        return response.json()


def _select_distribution(
    distributions: list[dict],
    platform: str | None = None,
) -> dict | None:
    """Select the best distribution for the current platform.

    Args:
        distributions: List of distribution dicts
        platform: Preferred platform tag (or None for auto-detect)

    Returns:
        Selected distribution dict, or None if no suitable distribution found
    """
    if not distributions:
        return None

    # If platform specified, look for exact match
    if platform:
        for dist in distributions:
            if dist.get("platform_tag") == platform:
                return dist

    # Prefer py3-none-any (pure Python, universal)
    for dist in distributions:
        if dist.get("platform_tag") == "py3-none-any":
            return dist

    # Fall back to first .island file
    for dist in distributions:
        filename = dist.get("filename", "")
        if filename.endswith(".island"):
            return dist

    # Last resort: first distribution
    return distributions[0] if distributions else None


@click.command()
@click.argument("package_name")
@click.option(
    "--version",
    "-v",
    "version",
    default=None,
    help="Specific version to install (default: latest).",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Output directory for downloaded package.",
)
@click.option(
    "--platform",
    "-p",
    default=None,
    help="Platform tag to download (e.g., py3-none-any).",
)
@click.option(
    "--repository",
    "-r",
    default=DEFAULT_REPOSITORY,
    envvar="ISLAND_REPOSITORY",
    help="Package Index URL.",
)
@click.option(
    "--no-verify",
    is_flag=True,
    help="Skip checksum verification (NOT RECOMMENDED).",
)
@pass_context
def install(
    ctx: Context,
    package_name: str,
    version: str | None,
    output_dir: Path | None,
    platform: str | None,
    repository: str,
    no_verify: bool,
) -> None:
    """Install an Island package from the registry.

    Downloads the package directly from the external URL (e.g., GitHub Releases)
    and verifies the SHA256 checksum against the registry-provided value.

    \b
    Examples:
        # Install latest version
        island install my-game

        # Install specific version
        island install my-game --version 1.0.0

        # Install to specific directory
        island install my-game --output ./packages

        # Install specific platform
        island install my-game --platform py3-none-any
    """
    if no_verify:
        echo_warning(
            "Checksum verification disabled. "
            "This is NOT RECOMMENDED and may expose you to security risks."
        )

    # Determine output directory
    if output_dir is None:
        output_dir = Path.cwd()

    echo_info(f"Fetching package info for {package_name}...")

    try:
        # Get package/version metadata
        if version:
            metadata = _get_package_metadata(repository, package_name, version)
            selected_version = version
        else:
            # Get package info to find latest version
            pkg_info = _get_package_metadata(repository, package_name)
            latest = pkg_info.get("latest_version")
            if not latest:
                echo_error(f"No versions available for {package_name}")
                raise SystemExit(1)
            selected_version = str(latest)
            # Now get the version metadata
            metadata = _get_package_metadata(repository, package_name, selected_version)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            if version:
                echo_error(f"Package {package_name} version {version} not found.")
            else:
                echo_error(f"Package {package_name} not found.")
        else:
            echo_error(f"Failed to fetch package info: {e}")
        raise SystemExit(1) from e
    except httpx.RequestError as e:
        echo_error(f"Network error: {e}")
        raise SystemExit(1) from e

    # Get distributions
    distributions = metadata.get("distributions", [])
    if not distributions:
        echo_error(f"No distributions available for {package_name} {selected_version}")
        raise SystemExit(1)

    # Select distribution
    dist = _select_distribution(distributions, platform)
    if dist is None:
        echo_error(f"No suitable distribution found for platform: {platform or 'any'}")
        raise SystemExit(1)

    # Check URL status
    url_status = dist.get("url_status", "active")
    if url_status != "active":
        echo_warning(f"Distribution URL status: {url_status}")

    filename = dist["filename"]
    external_url = dist["external_url"]
    expected_sha256 = dist["sha256"]
    expected_size = dist.get("size", 0)

    echo_info(f"Package: {package_name} v{selected_version}")
    echo_info(f"File: {filename}")
    echo_info(f"Size: {expected_size:,} bytes")
    echo_info(f"Downloading from: {external_url}")

    output_path = output_dir / filename

    try:
        if no_verify:
            # Download without verification
            with httpx.Client(follow_redirects=True, timeout=300.0) as client:
                response = client.get(external_url)
                response.raise_for_status()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(response.content)
                downloaded_size = len(response.content)
        else:
            # Download with checksum verification
            downloaded_size = download_and_verify(
                url=external_url,
                expected_sha256=expected_sha256,
                output_path=output_path,
            )

        echo_success(f"\nSuccessfully installed {package_name} v{selected_version}")
        echo_info(f"Downloaded: {downloaded_size:,} bytes")
        echo_info(f"Location: {output_path}")

        if not no_verify:
            echo_info(f"Checksum verified: {expected_sha256[:16]}...")

    except ChecksumMismatchError as e:
        echo_error(str(e))
        # Clean up partial download
        if output_path.exists():
            output_path.unlink()
        raise SystemExit(1) from e
    except httpx.HTTPStatusError as e:
        echo_error(f"Download failed: HTTP {e.response.status_code}")
        raise SystemExit(1) from e
    except httpx.RequestError as e:
        echo_error(f"Download failed: {e}")
        raise SystemExit(1) from e
