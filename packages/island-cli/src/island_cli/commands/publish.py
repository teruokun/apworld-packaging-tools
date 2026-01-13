# SPDX-License-Identifier: MIT
"""Publish Island packages to the Package Index.

DEPRECATED: This command is deprecated. Use 'island register' instead.

The registry has migrated to a Go-style model where packages are hosted
externally (e.g., on GitHub Releases) and only metadata/URLs are registered
with the registry. The 'publish' command's file upload functionality is
no longer supported.

Use 'island register' to register your package with external URLs:

    island register \\
        --url https://github.com/user/repo/releases/download/v1.0.0/my_game-1.0.0-py3-none-any.island \\
        --file dist/my_game-1.0.0-py3-none-any.island
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import click
import httpx

from ..config import ConfigError
from ..main import Context, echo_error, echo_info, echo_success, echo_warning, pass_context


DEFAULT_REPOSITORY = "https://islands.archipelago.gg/v1"


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _get_token_from_env() -> str | None:
    """Get API token from environment variable."""
    return os.environ.get("ISLAND_TOKEN") or os.environ.get("ARCHIPELAGO_TOKEN")


def _find_distributions(dist_dir: Path, name: str, version: str) -> list[Path]:
    """Find distribution files matching the package name and version."""
    distributions: list[Path] = []

    # Look for .island files
    for island in dist_dir.glob("*.island"):
        if name.replace("-", "_") in island.name and version in island.name:
            distributions.append(island)

    # Look for .tar.gz files
    for sdist in dist_dir.glob("*.tar.gz"):
        if name.replace("-", "_") in sdist.name and version in sdist.name:
            distributions.append(sdist)

    return distributions


@click.command(deprecated=True)
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
    token: str | None,
    dist_dir: Path,
    files: tuple[Path, ...],
    skip_existing: bool,
    dry_run: bool,
) -> None:
    """Upload Island packages to the Package Index.

    DEPRECATED: This command is deprecated. Use 'island register' instead.

    The registry has migrated to a Go-style model where packages are hosted
    externally (e.g., on GitHub Releases) and only metadata/URLs are registered.

    \b
    Migration guide:
        1. Upload your distributions to GitHub Releases (or similar)
        2. Use 'island register' with the external URLs:

           island register \\
               --url https://github.com/user/repo/releases/download/v1.0.0/pkg.island \\
               --file dist/pkg.island

    \b
    Old usage (no longer supported):
        island publish                          # Upload from dist/
        island publish -f my_game-1.0.0.island  # Upload specific file
    """
    # Show deprecation warning
    echo_warning(
        "DEPRECATED: The 'publish' command is deprecated and will be removed in a future version."
    )
    echo_warning("The registry no longer accepts file uploads. Use 'island register' instead.")
    echo_info("")
    echo_info("Migration guide:")
    echo_info("  1. Upload your distributions to GitHub Releases (or similar hosting)")
    echo_info("  2. Use 'island register' with the external URLs:")
    echo_info("")
    echo_info("     island register \\")
    echo_info("         --url https://github.com/user/repo/releases/download/v1.0.0/pkg.island \\")
    echo_info("         --file dist/pkg.island")
    echo_info("")

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
        package_name = cli_config.name
        package_version = cli_config.version
    except (ConfigError, FileNotFoundError):
        # If no config, we need files to be specified
        if not files:
            echo_error("No pyproject.toml found. Use --file to specify distributions to upload.")
            raise SystemExit(1)
        package_name = ""
        package_version = ""
        cli_config = None

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
            echo_info("Run 'island build' first to create distributions.")
            raise SystemExit(1)

        if package_name and package_version:
            distributions = _find_distributions(dist_dir, package_name, package_version)
        else:
            # Find all distributions
            distributions = list(dist_dir.glob("*.island")) + list(dist_dir.glob("*.tar.gz"))

    if not distributions:
        echo_error("No distributions found to upload.")
        echo_info("Run 'island build' first to create distributions.")
        raise SystemExit(1)

    echo_info(f"Repository: {repository}")
    echo_info(f"Distributions to upload: {len(distributions)}")

    for dist_path in distributions:
        echo_info(f"  - {dist_path.name} ({dist_path.stat().st_size:,} bytes)")

    if dry_run:
        echo_warning("\nDry run - no files will be uploaded.")
        echo_warning("Note: File uploads are no longer supported by the registry.")
        echo_success("Upload preview complete.")
        return

    # Attempt upload (will fail with registry that no longer supports uploads)
    uploaded = 0
    failed = 0

    for dist_path in distributions:
        echo_info(f"\nUploading: {dist_path.name}")

        # Compute checksum
        checksum = _compute_sha256(dist_path)
        echo_info(f"  SHA256: {checksum}")

        # Extract package name from filename
        filename = dist_path.name
        if filename.endswith(".island"):
            # Format: name-version-python-abi-platform.island
            parts = filename.rsplit("-", 3)
            if len(parts) >= 2:
                pkg_name = parts[0]
            else:
                pkg_name = filename.replace(".island", "")
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
                echo_success("  Uploaded successfully!")
                uploaded += 1
            elif response.status_code == 404:
                # Upload endpoint no longer exists
                echo_error("  Upload endpoint not found. The registry no longer accepts uploads.")
                echo_info("  Use 'island register' with external URLs instead.")
                failed += 1
            elif response.status_code == 409:
                # Version already exists
                if skip_existing:
                    echo_warning("  Version already exists, skipping.")
                    uploaded += 1
                else:
                    echo_error("  Version already exists. Use --skip-existing to ignore.")
                    failed += 1
            elif response.status_code == 401:
                echo_error("  Authentication failed. Check your token.")
                failed += 1
            elif response.status_code == 403:
                echo_error("  Permission denied. You may not own this package.")
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
            echo_error("  Connection failed. Check the repository URL.")
            failed += 1
        except httpx.TimeoutException:
            echo_error("  Upload timed out.")
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
