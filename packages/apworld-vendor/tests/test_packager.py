# SPDX-License-Identifier: MIT
"""Tests for the vendoring packager module."""

import json
import tempfile
from pathlib import Path

import pytest

from apworld_vendor.config import VendorConfig, VendoredPackage, VendorResult
from apworld_vendor.packager import (
    DependencyDownloadError,
    _get_top_level_modules,
    _normalize_package_name,
    _parse_requirement,
    create_vendor_manifest,
)


class TestNormalizePackageName:
    """Tests for _normalize_package_name function."""

    def test_lowercase(self):
        """Package names should be lowercased."""
        assert _normalize_package_name("PyYAML") == "pyyaml"

    def test_hyphens_normalized(self):
        """Hyphens should be normalized."""
        assert _normalize_package_name("my-package") == "my-package"

    def test_underscores_to_hyphens(self):
        """Underscores should be converted to hyphens."""
        assert _normalize_package_name("my_package") == "my-package"

    def test_periods_to_hyphens(self):
        """Periods should be converted to hyphens."""
        assert _normalize_package_name("my.package") == "my-package"

    def test_multiple_separators(self):
        """Multiple separators should be collapsed."""
        assert _normalize_package_name("my--package") == "my-package"
        assert _normalize_package_name("my__package") == "my-package"


class TestParseRequirement:
    """Tests for _parse_requirement function."""

    def test_simple_name(self):
        """Simple package name should be extracted."""
        assert _parse_requirement("pyyaml") == "pyyaml"

    def test_with_version(self):
        """Version specifier should be stripped."""
        assert _parse_requirement("pyyaml>=6.0") == "pyyaml"
        assert _parse_requirement("pyyaml==6.0.1") == "pyyaml"
        assert _parse_requirement("pyyaml~=6.0") == "pyyaml"

    def test_with_extras(self):
        """Extras should be stripped."""
        assert _parse_requirement("requests[security]") == "requests"
        assert _parse_requirement("requests[security,socks]>=2.0") == "requests"

    def test_with_environment_marker(self):
        """Environment markers should be stripped."""
        assert _parse_requirement("pyyaml>=6.0; python_version >= '3.10'") == "pyyaml"

    def test_normalized(self):
        """Package name should be normalized."""
        assert _parse_requirement("PyYAML>=6.0") == "pyyaml"


class TestGetTopLevelModules:
    """Tests for _get_top_level_modules function."""

    def test_finds_packages(self):
        """Should find directories with __init__.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = Path(tmpdir)
            # Create a package
            (pkg_dir / "mypackage").mkdir()
            (pkg_dir / "mypackage" / "__init__.py").touch()

            modules = _get_top_level_modules(pkg_dir)
            assert "mypackage" in modules

    def test_finds_modules(self):
        """Should find .py files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = Path(tmpdir)
            # Create a module
            (pkg_dir / "mymodule.py").write_text("# module")

            modules = _get_top_level_modules(pkg_dir)
            assert "mymodule" in modules

    def test_ignores_init(self):
        """Should ignore __init__.py as a module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = Path(tmpdir)
            (pkg_dir / "__init__.py").write_text("# init")

            modules = _get_top_level_modules(pkg_dir)
            assert "__init__" not in modules

    def test_reads_top_level_txt(self):
        """Should read top_level.txt from dist-info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = Path(tmpdir)
            # Create dist-info with top_level.txt
            dist_info = pkg_dir / "mypackage-1.0.0.dist-info"
            dist_info.mkdir()
            (dist_info / "top_level.txt").write_text("mypackage\nmymodule\n")

            modules = _get_top_level_modules(pkg_dir)
            assert "mypackage" in modules
            assert "mymodule" in modules


class TestCreateVendorManifest:
    """Tests for create_vendor_manifest function."""

    def test_creates_manifest_file(self):
        """Should create a JSON manifest file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = VendorResult(
                packages=[
                    VendoredPackage(
                        name="pyyaml",
                        version="6.0.1",
                        source_path=Path(tmpdir),
                        top_level_modules=["yaml"],
                    ),
                    VendoredPackage(
                        name="requests",
                        version="2.28.0",
                        source_path=Path(tmpdir),
                        top_level_modules=["requests"],
                    ),
                ]
            )

            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            assert manifest_path.exists()
            manifest = json.loads(manifest_path.read_text())
            assert "vendored_packages" in manifest
            assert "pyyaml" in manifest["vendored_packages"]
            assert manifest["vendored_packages"]["pyyaml"]["version"] == "6.0.1"
            assert manifest["vendored_packages"]["pyyaml"]["modules"] == ["yaml"]

    def test_creates_parent_directories(self):
        """Should create parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = VendorResult()
            manifest_path = Path(tmpdir) / "subdir" / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)
            assert manifest_path.exists()


class TestVendorDependencies:
    """Tests for vendor_dependencies function.

    Note: These tests are limited because they would require network access
    to actually download packages. We test the configuration and error handling.
    """

    def test_empty_dependencies_returns_success(self):
        """Empty dependencies should return successful result."""
        from apworld_vendor.packager import vendor_dependencies

        config = VendorConfig(package_name="my_game", dependencies=[])

        with tempfile.TemporaryDirectory() as tmpdir:
            result = vendor_dependencies(config, tmpdir)
            assert result.success is True
            assert result.packages == []

    def test_excluded_dependencies_not_vendored(self):
        """Excluded dependencies should not be vendored."""
        from apworld_vendor.packager import vendor_dependencies

        config = VendorConfig(
            package_name="my_game",
            dependencies=["typing_extensions"],
            exclude=["typing_extensions"],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = vendor_dependencies(config, tmpdir)
            # Should succeed but vendor nothing
            assert result.success is True
            assert result.packages == []

    def test_core_ap_dependencies_not_vendored(self):
        """Core AP modules should not be vendored."""
        from apworld_vendor.packager import vendor_dependencies

        config = VendorConfig(
            package_name="my_game",
            dependencies=["BaseClasses"],  # This is a Core AP module
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = vendor_dependencies(config, tmpdir)
            # Should succeed but vendor nothing
            assert result.success is True
            assert result.packages == []


class TestDependencyDownloadError:
    """Tests for DependencyDownloadError exception."""

    def test_error_message(self):
        """Error should contain message."""
        error = DependencyDownloadError("Failed to download pyyaml")
        assert "Failed to download pyyaml" in str(error)
