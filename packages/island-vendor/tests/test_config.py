# SPDX-License-Identifier: MIT
"""Tests for the vendor configuration module."""

import pytest

from island_vendor.config import (
    CORE_AP_MODULES,
    VendorConfig,
    VendorConfigError,
    VendoredPackage,
    VendorResult,
)


class TestVendorConfig:
    """Tests for VendorConfig dataclass."""

    def test_minimal_config(self):
        """Minimal config with just package name should work."""
        config = VendorConfig(package_name="my_game")
        assert config.package_name == "my_game"
        assert config.dependencies == []
        assert config.exclude == []
        assert config.namespace == "_vendor"

    def test_full_config(self):
        """Full config with all fields should work."""
        config = VendorConfig(
            package_name="pokemon_emerald",
            dependencies=["pyyaml>=6.0", "requests"],
            exclude=["typing_extensions"],
            namespace="_deps",
        )
        assert config.package_name == "pokemon_emerald"
        assert config.dependencies == ["pyyaml>=6.0", "requests"]
        assert config.exclude == ["typing_extensions"]
        assert config.namespace == "_deps"

    def test_empty_package_name_raises_error(self):
        """Empty package name should raise VendorConfigError."""
        with pytest.raises(VendorConfigError, match="package_name is required"):
            VendorConfig(package_name="")

    def test_invalid_package_name_raises_error(self):
        """Invalid package name should raise VendorConfigError."""
        with pytest.raises(VendorConfigError, match="Invalid package_name"):
            VendorConfig(package_name="my game!")

    def test_vendor_namespace_property(self):
        """vendor_namespace should return correct format."""
        config = VendorConfig(package_name="my_game")
        assert config.vendor_namespace == "my_game._vendor"

    def test_vendor_namespace_normalizes_hyphens(self):
        """vendor_namespace should convert hyphens to underscores."""
        config = VendorConfig(package_name="my-game")
        assert config.vendor_namespace == "my_game._vendor"

    def test_vendor_namespace_custom_namespace(self):
        """vendor_namespace should use custom namespace."""
        config = VendorConfig(package_name="my_game", namespace="_deps")
        assert config.vendor_namespace == "my_game._deps"

    def test_should_vendor_returns_true_for_normal_package(self):
        """should_vendor should return True for normal packages."""
        config = VendorConfig(package_name="my_game")
        assert config.should_vendor("pyyaml") is True
        assert config.should_vendor("requests") is True

    def test_should_vendor_returns_false_for_core_ap(self):
        """should_vendor should return False for Core AP modules."""
        config = VendorConfig(package_name="my_game")
        assert config.should_vendor("BaseClasses") is False
        assert config.should_vendor("Options") is False
        assert config.should_vendor("worlds") is False

    def test_should_vendor_returns_false_for_excluded(self):
        """should_vendor should return False for excluded packages."""
        config = VendorConfig(
            package_name="my_game",
            exclude=["typing_extensions", "colorama"],
        )
        assert config.should_vendor("typing_extensions") is False
        assert config.should_vendor("colorama") is False
        assert config.should_vendor("pyyaml") is True

    def test_is_core_ap_module_simple(self):
        """is_core_ap_module should detect Core AP modules."""
        config = VendorConfig(package_name="my_game")
        assert config.is_core_ap_module("BaseClasses") is True
        assert config.is_core_ap_module("Options") is True
        assert config.is_core_ap_module("pyyaml") is False

    def test_is_core_ap_module_dotted_path(self):
        """is_core_ap_module should handle dotted paths."""
        config = VendorConfig(package_name="my_game")
        assert config.is_core_ap_module("worlds.generic") is True
        assert config.is_core_ap_module("worlds.generic.Rules") is True
        assert config.is_core_ap_module("pyyaml.parser") is False


class TestVendorConfigFromPyprojectDict:
    """Tests for VendorConfig.from_pyproject_dict."""

    def test_minimal_pyproject(self):
        """Minimal pyproject.toml should work."""
        pyproject = {
            "project": {
                "name": "my-game",
            }
        }
        config = VendorConfig.from_pyproject_dict(pyproject)
        assert config.package_name == "my-game"
        assert config.dependencies == []
        assert config.exclude == []

    def test_with_dependencies(self):
        """Dependencies should be extracted from project.dependencies."""
        pyproject = {
            "project": {
                "name": "my-game",
                "dependencies": ["pyyaml>=6.0", "requests"],
            }
        }
        config = VendorConfig.from_pyproject_dict(pyproject)
        assert config.dependencies == ["pyyaml>=6.0", "requests"]

    def test_with_vendor_config(self):
        """Vendor config should be extracted from tool.island.vendor."""
        pyproject = {
            "project": {
                "name": "my-game",
                "dependencies": ["pyyaml>=6.0"],
            },
            "tool": {
                "island": {
                    "vendor": {
                        "exclude": ["typing_extensions"],
                        "namespace": "_deps",
                    }
                }
            },
        }
        config = VendorConfig.from_pyproject_dict(pyproject)
        assert config.exclude == ["typing_extensions"]
        assert config.namespace == "_deps"

    def test_extra_exclude(self):
        """extra_exclude should be added to exclude list."""
        pyproject = {
            "project": {
                "name": "my-game",
            },
            "tool": {
                "island": {
                    "vendor": {
                        "exclude": ["typing_extensions"],
                    }
                }
            },
        }
        config = VendorConfig.from_pyproject_dict(pyproject, extra_exclude=["colorama"])
        assert "typing_extensions" in config.exclude
        assert "colorama" in config.exclude

    def test_missing_project_name_raises_error(self):
        """Missing project.name should raise VendorConfigError."""
        pyproject = {"project": {}}
        with pytest.raises(VendorConfigError, match="Missing required field"):
            VendorConfig.from_pyproject_dict(pyproject)

    def test_missing_project_section_raises_error(self):
        """Missing project section should raise VendorConfigError."""
        pyproject = {}
        with pytest.raises(VendorConfigError, match="Missing required field"):
            VendorConfig.from_pyproject_dict(pyproject)


class TestVendoredPackage:
    """Tests for VendoredPackage dataclass."""

    def test_vendored_package_fields(self):
        """VendoredPackage should have expected fields."""
        from pathlib import Path

        pkg = VendoredPackage(
            name="pyyaml",
            version="6.0.1",
            source_path=Path("/tmp/vendor"),
            top_level_modules=["yaml"],
        )
        assert pkg.name == "pyyaml"
        assert pkg.version == "6.0.1"
        assert pkg.source_path == Path("/tmp/vendor")
        assert pkg.top_level_modules == ["yaml"]


class TestVendorResult:
    """Tests for VendorResult dataclass."""

    def test_empty_result_is_success(self):
        """Empty result should be successful."""
        result = VendorResult()
        assert result.success is True
        assert result.packages == []
        assert result.errors == []

    def test_result_with_errors_is_not_success(self):
        """Result with errors should not be successful."""
        result = VendorResult(errors=["Failed to download package"])
        assert result.success is False

    def test_get_vendored_module_names(self):
        """get_vendored_module_names should return all module names."""
        from pathlib import Path

        result = VendorResult(
            packages=[
                VendoredPackage(
                    name="pyyaml",
                    version="6.0",
                    source_path=Path("/tmp"),
                    top_level_modules=["yaml"],
                ),
                VendoredPackage(
                    name="requests",
                    version="2.28",
                    source_path=Path("/tmp"),
                    top_level_modules=["requests", "urllib3"],
                ),
            ]
        )
        modules = result.get_vendored_module_names()
        assert modules == {"yaml", "requests", "urllib3"}


class TestCoreAPModules:
    """Tests for CORE_AP_MODULES constant."""

    def test_contains_expected_modules(self):
        """CORE_AP_MODULES should contain expected modules."""
        assert "BaseClasses" in CORE_AP_MODULES
        assert "Options" in CORE_AP_MODULES
        assert "Fill" in CORE_AP_MODULES
        assert "worlds" in CORE_AP_MODULES
        assert "Utils" in CORE_AP_MODULES

    def test_is_frozenset(self):
        """CORE_AP_MODULES should be a frozenset."""
        assert isinstance(CORE_AP_MODULES, frozenset)
