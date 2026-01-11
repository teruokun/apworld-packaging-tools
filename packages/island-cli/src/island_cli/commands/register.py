# SPDX-License-Identifier: MIT
"""Register Island packages with the Package Index using external URLs."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import click
import httpx

from ..config import ConfigError
from ..main import Context, echo_error, echo_info, echo_success, echo_warning, pass_context


DEFAULT_REPOSITORY = "https://api.archipelago.gg/v1/island"


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        SHA256 hash as lowercase hex string (64 characters)
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _get_token_from_env() -> str | None:
    """Get API token from environment variable."""
    return os.environ.get("ISLAND_TOKEN") or os.environ.get("ARCHIPELAGO_TOKEN")


def _extract_platform_tag(filename: str) -> str:
    """Extract platform tag from distribution filename.

    Args:
        filename: Distribution filename (e.g., my_game-1.0.0-py3-none-any.island)

    Returns:
        Platform tag (e.g., py3-none-any) or 'source' for source distributions
    """
    if filename.endswith(".tar.gz"):
        return "source"

    if filename.endswith(".island"):
        # Format: name-version-python-abi-platform.island
        # e.g., my_game-1.0.0-py3-none-any.island
        base = filename[:-7]  # Remove .island
        parts = base.rsplit("-", 3)
        if len(parts) >= 4:
            # Last 3 parts are python-abi-platform
            return f"{parts[-3]}-{parts[-2]}-{parts[-1]}"

    # Default fallback
    return "py3-none-any"


def _validate_checksum_format(checksum: str) -> bool:
    """Validate that a checksum is 64 lowercase hex characters.

    Args:
        checksum: The checksum string to validate

    Returns:
        True if valid, False otherwise
    """
    return bool(re.match(r"^[0-9a-f]{64}$", checksum.lower()))


def _get_entry_points_from_config(config) -> dict[str, str]:
    """Extract entry points from config.

    The entry points should be in the format expected by the registry API.
    """
    # Try to read entry points from pyproject.toml directly
    pyproject_path = config.project_dir / "pyproject.toml"
    if pyproject_path.exists():
        import sys

        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)

        # Look for entry points in project.entry-points.ap-island
        entry_points = pyproject.get("project", {}).get("entry-points", {}).get("ap-island", {})
        if entry_points:
            return entry_points

    # Fallback: construct from game name
    # This is a reasonable default for most island packages
    if config.name and config.game_name:
        module_name = config.name.replace("-", "_")
        return {config.game_name: f"{module_name}:World"}

    return {}


@click.command()
@click.option(
    "--url",
    "-u",
    "urls",
    multiple=True,
    help="Asset URL (can specify multiple). Must be HTTPS.",
)
@click.option(
    "--checksum",
    "-c",
    "checksums",
    multiple=True,
    help="SHA256 checksum for each URL (64 lowercase hex characters).",
)
@click.option(
    "--file",
    "-f",
    "files",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    multiple=True,
    help="Local file to compute checksum from (paired with --url).",
)
@click.option(
    "--repository",
    "-r",
    default=DEFAULT_REPOSITORY,
    envvar="ISLAND_REPOSITORY",
    help="Package Index URL.",
)
@click.option(
    "--token",
    "-t",
    envvar="ISLAND_TOKEN",
    help="API token for authentication.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show registration payload without submitting.",
)
@pass_context
def register(
    ctx: Context,
    urls: tuple[str, ...],
    checksums: tuple[str, ...],
    files: tuple[Path, ...],
    repository: str,
    token: str | None,
    dry_run: bool,
) -> None:
    """Register package with external asset URLs.

    Register your package by providing URLs to externally-hosted assets
    (e.g., GitHub release artifacts) along with their SHA256 checksums.

    The registry will verify the URLs are accessible and checksums match
    before accepting the registration.

    \b
    Examples:
        # Register with explicit checksums
        island register \\
            --url https://github.com/user/repo/releases/download/v1.0.0/my_game-1.0.0-py3-none-any.island \\
            --checksum abc123...

        # Compute checksums from local files
        island register \\
            --url https://github.com/user/repo/releases/download/v1.0.0/my_game-1.0.0-py3-none-any.island \\
            --file dist/my_game-1.0.0-py3-none-any.island

        # Register multiple distributions
        island register \\
            --url https://...island --file dist/...island \\
            --url https://...tar.gz --file dist/...tar.gz
    """
    # Validate we have at least one URL
    if not urls:
        echo_error("At least one --url is required.")
        raise SystemExit(1)

    # Get authentication token
    if token is None:
        token = _get_token_from_env()

    if token is None and not dry_run:
        echo_error(
            "Authentication required. Provide --token or set ISLAND_TOKEN environment variable."
        )
        raise SystemExit(1)

    # Load configuration to get package info
    try:
        cli_config = ctx.load_config()
    except (ConfigError, FileNotFoundError) as e:
        echo_error(f"Could not load project configuration: {e}")
        echo_info("Run this command from a directory with pyproject.toml.")
        raise SystemExit(1) from e

    # Validate required config fields
    if not cli_config.name:
        echo_error("Package name not found in pyproject.toml.")
        raise SystemExit(1)

    if not cli_config.version:
        echo_error("Package version not found in pyproject.toml.")
        raise SystemExit(1)

    if not cli_config.game_name:
        echo_error("Game name not found in pyproject.toml (tool.island.game).")
        raise SystemExit(1)

    if not cli_config.minimum_ap_version:
        echo_error(
            "Minimum AP version not found in pyproject.toml (tool.island.minimum_ap_version)."
        )
        raise SystemExit(1)

    # Get entry points
    entry_points = _get_entry_points_from_config(cli_config)
    if not entry_points:
        echo_error("No entry points found. Add [project.entry-points.ap-island] to pyproject.toml.")
        raise SystemExit(1)

    # Build distribution list
    distributions = []
    for i, asset_url in enumerate(urls):
        # Validate URL is HTTPS
        if not asset_url.startswith("https://"):
            echo_error(f"URL must use HTTPS: {asset_url}")
            raise SystemExit(1)

        # Extract filename from URL
        filename = asset_url.rsplit("/", 1)[-1]

        # Get checksum from --checksum or compute from --file
        sha256: str | None = None
        size: int | None = None

        if i < len(checksums):
            sha256 = checksums[i].lower()
            if not _validate_checksum_format(sha256):
                echo_error(
                    f"Invalid checksum format for {filename}: must be 64 lowercase hex characters."
                )
                raise SystemExit(1)

        if i < len(files):
            file_path = files[i]
            computed_sha256 = _compute_sha256(file_path)
            size = file_path.stat().st_size

            if sha256 is not None:
                # Verify computed matches provided
                if sha256 != computed_sha256:
                    echo_error(
                        f"Checksum mismatch for {filename}:\n"
                        f"  Provided: {sha256}\n"
                        f"  Computed: {computed_sha256}"
                    )
                    raise SystemExit(1)
            else:
                sha256 = computed_sha256

        if sha256 is None:
            echo_error(f"No checksum provided for {asset_url}. Use --checksum or --file.")
            raise SystemExit(1)

        if size is None:
            echo_error(f"File size unknown for {asset_url}. Use --file to provide the local file.")
            raise SystemExit(1)

        # Determine platform tag from filename
        platform_tag = _extract_platform_tag(filename)

        distributions.append(
            {
                "filename": filename,
                "url": asset_url,
                "sha256": sha256,
                "size": size,
                "platform_tag": platform_tag,
            }
        )

    # Build registration payload
    payload = {
        "name": cli_config.name,
        "version": cli_config.version,
        "game": cli_config.game_name,
        "description": cli_config.description or f"Island package for {cli_config.game_name}",
        "authors": cli_config.authors or ["Unknown"],
        "minimum_ap_version": cli_config.minimum_ap_version,
        "maximum_ap_version": cli_config.maximum_ap_version or None,
        "keywords": cli_config.keywords or [],
        "homepage": cli_config.homepage or None,
        "repository": cli_config.repository or None,
        "license": cli_config.license or None,
        "entry_points": entry_points,
        "distributions": distributions,
    }

    # Display info
    echo_info(f"Package: {cli_config.name} v{cli_config.version}")
    echo_info(f"Game: {cli_config.game_name}")
    echo_info(f"Repository: {repository}")
    echo_info(f"Distributions: {len(distributions)}")
    for dist in distributions:
        echo_info(f"  - {dist['filename']} ({dist['size']:,} bytes)")
        echo_info(f"    SHA256: {dist['sha256']}")

    if dry_run:
        echo_warning("\nDry run - registration payload:")
        echo_info(json.dumps(payload, indent=2))
        echo_success("\nDry run complete. No registration submitted.")
        return

    # Submit registration
    register_url = f"{repository.rstrip('/')}/register"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    echo_info(f"\nSubmitting registration to {register_url}...")

    try:
        response = httpx.post(
            register_url,
            json=payload,
            headers=headers,
            timeout=60.0,
        )

        if response.status_code == 200 or response.status_code == 201:
            result = response.json()
            echo_success("\nPackage registered successfully!")
            echo_info(f"  Package: {result.get('package_name', cli_config.name)}")
            echo_info(f"  Version: {result.get('version', cli_config.version)}")
            if "registry_url" in result:
                echo_info(f"  URL: {result['registry_url']}")
        elif response.status_code == 400:
            try:
                error_data = response.json()
                error_msg = error_data.get("detail", response.text)
            except Exception:
                error_msg = response.text
            echo_error(f"Registration rejected: {error_msg}")
            raise SystemExit(1)
        elif response.status_code == 401:
            echo_error("Authentication failed. Check your token.")
            raise SystemExit(1)
        elif response.status_code == 403:
            echo_error("Permission denied. You may not own this package.")
            raise SystemExit(1)
        elif response.status_code == 409:
            echo_error("Version already exists. Use a new version number.")
            raise SystemExit(1)
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("detail", response.text)
            except Exception:
                error_msg = response.text
            echo_error(f"Registration failed ({response.status_code}): {error_msg}")
            raise SystemExit(1)

    except httpx.ConnectError as e:
        echo_error("Connection failed. Check the repository URL.")
        raise SystemExit(1) from e
    except httpx.TimeoutException as e:
        echo_error("Request timed out.")
        raise SystemExit(1) from e
    except Exception as e:
        echo_error(f"Registration error: {e}")
        raise SystemExit(1) from e
