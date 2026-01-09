# SPDX-License-Identifier: MIT
"""Publish APWorld packages to the Package Index."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

import click
import httpx

from ..config import ConfigError, load_config
from ..main import echo_error, echo_info, echo_success, echo_warning, pass_context, Context


DEFAULT_REPOSITORY = "https://api.archipelago.gg/v1"


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _get_token_from_env() -> Optional[str]:
    """Get API token from environment variable."""
    return os.environ.get("APWORLD_TOKEN") or os.environ.get("ARCHIPELAGO_TOKEN")


def _find_distributions(dist_dir: Path, name: str, version: str) -> list[Path]:
    """Find distribution files matching the package name and version."""
    distributions: list[Path] = []

    # Look for .apworld files
    for apworld in dist_dir.glob("*.apworld"):
        if name.replace("-", "_") in apworld.name and version in apworld.name:
            distributions.append(apworld)

    # Look for .tar.gz files
    for sdist in dist_dir.glob("*.tar.gz"):
        if name.replace("-", "_") in sdist.name and version in sdist.name:
            distributions.append(sdist)

    return distributions


@click.command()
@click.option(
    "--repository",
    "-r",
    default=DEFAULT_REPOSITORY,
    envvar="APWORLD_REPOSITORY",
    help="Package Index URL.",
)
@click.option(
    "--token",
    "-t",
    envvar="APWORLD_TOKEN",
    help="API token for authentication.",
)
@click.option(
    "--dist-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default="dist",
    help="Directory containing distributions to upload.",
)
@click.option(
    "--file",
    "-f",
    "files",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    multiple=True,
    help="Specific file(s) to upload.",
)
@click.option(
    "--skip-existing",
    is_flag=True,
    help="Skip upload if version already exists.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be uploaded without actually uploading.",
)
@pass_context
def publish(
    ctx: Context,
    repository: str,
    token: Optional[str],
    dist_dir: Path,
    files: tuple[Path, ...],
    skip_existing: bool,
    dry_run: bool,
) -> None:
    """Upload APWorld packages to the Package Index.

    Uploads .apworld and .tar.gz distributions to the repository.
    Requires authentication via --token or APWORLD_TOKEN environment variable.

    \b
    Examples:
        apworld publish                          # Upload from dist/
        apworld publish -f my_game-1.0.0.apworld # Upload specific file
        apworld publish --dry-run                # Preview upload
        apworld publish -r https://custom.repo   # Use custom repository
    """
    # Get authentication token
    if token is None:
        token = _get_token_from_env()

    if token is None and not dry_run:
        echo_error(
            "Authentication required. Provide --token or set APWORLD_TOKEN environment variable."
        )
        raise SystemExit(1)

    # Load configuration to get package info
    try:
        cli_config = ctx.load_config()
        package_name = cli_config.name
        package_version = cli_config.version
    except (ConfigError, FileNotFoundError):
        # If no config, we need files to be specified
        if not files:
            echo_error("No pyproject.toml found. Use --file to specify distributions to upload.")
            raise SystemExit(1)
        package_name = ""
        package_version = ""

    # Determine files to upload
    distributions: list[Path] = []

    if files:
        distributions.extend(files)
    else:
        # Find distributions in dist directory
        project_dir = cli_config.project_dir if cli_config else Path.cwd()
        if not dist_dir.is_absolute():
            dist_dir = project_dir / dist_dir

        if not dist_dir.exists():
            echo_error(f"Distribution directory not found: {dist_dir}")
            echo_info("Run 'apworld build' first to create distributions.")
            raise SystemExit(1)

        if package_name and package_version:
            distributions = _find_distributions(dist_dir, package_name, package_version)
        else:
            # Find all distributions
            distributions = list(dist_dir.glob("*.apworld")) + list(dist_dir.glob("*.tar.gz"))

    if not distributions:
        echo_error("No distributions found to upload.")
        echo_info("Run 'apworld build' first to create distributions.")
        raise SystemExit(1)

    echo_info(f"Repository: {repository}")
    echo_info(f"Distributions to upload: {len(distributions)}")

    for dist_path in distributions:
        echo_info(f"  - {dist_path.name} ({dist_path.stat().st_size:,} bytes)")

    if dry_run:
        echo_warning("\nDry run - no files will be uploaded.")
        echo_success("Upload preview complete.")
        return

    # Upload each distribution
    uploaded = 0
    failed = 0

    for dist_path in distributions:
        echo_info(f"\nUploading: {dist_path.name}")

        # Compute checksum
        checksum = _compute_sha256(dist_path)
        echo_info(f"  SHA256: {checksum}")

        # Extract package name from filename
        filename = dist_path.name
        if filename.endswith(".apworld"):
            # Format: name-version-python-abi-platform.apworld
            parts = filename.rsplit("-", 3)
            if len(parts) >= 2:
                pkg_name = parts[0]
            else:
                pkg_name = filename.replace(".apworld", "")
        elif filename.endswith(".tar.gz"):
            # Format: name-version.tar.gz
            pkg_name = filename.replace(".tar.gz", "").rsplit("-", 1)[0]
        else:
            pkg_name = package_name or "unknown"

        # Prepare upload
        upload_url = f"{repository.rstrip('/')}/packages/{pkg_name}/upload"

        try:
            with open(dist_path, "rb") as f:
                files_data = {"file": (filename, f, "application/octet-stream")}
                headers = {
                    "Authorization": f"Bearer {token}",
                    "X-Checksum-SHA256": checksum,
                }

                response = httpx.post(
                    upload_url,
                    files=files_data,
                    headers=headers,
                    timeout=300.0,  # 5 minute timeout for large files
                )

            if response.status_code == 200 or response.status_code == 201:
                echo_success(f"  Uploaded successfully!")
                uploaded += 1
            elif response.status_code == 409:
                # Version already exists
                if skip_existing:
                    echo_warning(f"  Version already exists, skipping.")
                    uploaded += 1
                else:
                    echo_error(f"  Version already exists. Use --skip-existing to ignore.")
                    failed += 1
            elif response.status_code == 401:
                echo_error(f"  Authentication failed. Check your token.")
                failed += 1
            elif response.status_code == 403:
                echo_error(f"  Permission denied. You may not own this package.")
                failed += 1
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", response.text)
                except Exception:
                    error_msg = response.text
                echo_error(f"  Upload failed ({response.status_code}): {error_msg}")
                failed += 1

        except httpx.ConnectError:
            echo_error(f"  Connection failed. Check the repository URL.")
            failed += 1
        except httpx.TimeoutException:
            echo_error(f"  Upload timed out.")
            failed += 1
        except Exception as e:
            echo_error(f"  Upload error: {e}")
            failed += 1

    # Summary
    echo_info("")
    if failed == 0:
        echo_success(f"Published {uploaded} distribution(s) successfully!")
    else:
        echo_warning(f"Published {uploaded} distribution(s), {failed} failed.")
        raise SystemExit(1)
