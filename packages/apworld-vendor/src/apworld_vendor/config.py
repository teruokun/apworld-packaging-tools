# SPDX-License-Identifier: MIT
"""Vendoring configuration for APWorld packages.

This module provides configuration dataclasses for controlling how dependencies
are vendored into APWorld packages.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


# Core Archipelago modules that should never be vendored or rewritten
# These are provided by the Archipelago runtime
CORE_AP_MODULES = frozenset(
    {
        # Core framework modules
        "BaseClasses",
        "Options",
        "Fill",
        "Generate",
        "Main",
        "MultiServer",
        "NetUtils",
        "Utils",
        "Patch",
        "CommonClient",
        "Launcher",
        "settings",
        "entrance_rando",
        "kvui",
        # Worlds package
        "worlds",
        # Test framework
        "test",
    }
)


class VendorConfigError(Exception):
    """Raised when vendor configuration is invalid."""

    pass


@dataclass
class VendorConfig:
    """Configuration for dependency vendoring.

    Attributes:
        package_name: Name of the APWorld package (used for namespace)
        dependencies: List of dependencies to vendor (pip requirement format)
        exclude: List of packages to exclude from vendoring
        namespace: Namespace prefix for vendored packages (default: "_vendor")
        core_ap_modules: Set of Core AP modules to preserve unchanged
    """

    package_name: str
    dependencies: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    namespace: str = "_vendor"
    core_ap_modules: frozenset[str] = field(default_factory=lambda: CORE_AP_MODULES)

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.package_name:
            raise VendorConfigError("package_name is required")
        if not self.package_name.replace("_", "").replace("-", "").isalnum():
            raise VendorConfigError(
                f"Invalid package_name: {self.package_name!r}. "
                "Must contain only alphanumeric characters, underscores, or hyphens."
            )

    @property
    def vendor_namespace(self) -> str:
        """Get the full vendor namespace path.

        Returns:
            The namespace in format: {package_name}.{namespace}
            e.g., "my_game._vendor"
        """
        # Normalize package name to use underscores (Python module convention)
        normalized_name = self.package_name.replace("-", "_")
        return f"{normalized_name}.{self.namespace}"

    def should_vendor(self, package_name: str) -> bool:
        """Check if a package should be vendored.

        Args:
            package_name: Name of the package to check (can be normalized or original)

        Returns:
            True if the package should be vendored, False otherwise
        """
        # Normalize for comparison
        normalized = self._normalize_name(package_name)

        # Never vendor Core AP modules (check both original and normalized)
        if package_name in self.core_ap_modules:
            return False
        # Also check normalized version against normalized core modules
        normalized_core = {self._normalize_name(m) for m in self.core_ap_modules}
        if normalized in normalized_core:
            return False

        # Check explicit exclude list (both original and normalized)
        if package_name in self.exclude:
            return False
        normalized_exclude = {self._normalize_name(e) for e in self.exclude}
        if normalized in normalized_exclude:
            return False

        return True

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize a package name for comparison.

        PEP 503: Package names are case-insensitive and treat
        hyphens, underscores, and periods as equivalent.
        """
        import re

        return re.sub(r"[-_.]+", "-", name).lower()

    def is_core_ap_module(self, module_name: str) -> bool:
        """Check if a module is a Core AP module.

        Args:
            module_name: Name of the module (can be dotted path)

        Returns:
            True if this is a Core AP module that should not be rewritten
        """
        # Get the top-level module name
        top_level = module_name.split(".")[0]
        return top_level in self.core_ap_modules

    @classmethod
    def from_pyproject(
        cls,
        pyproject_path: str | Path,
        *,
        extra_exclude: list[str] | None = None,
    ) -> "VendorConfig":
        """Create VendorConfig from a pyproject.toml file.

        Reads the [project] section for package name and dependencies,
        and [tool.apworld.vendor] section for vendor-specific configuration.

        Args:
            pyproject_path: Path to pyproject.toml
            extra_exclude: Additional packages to exclude from vendoring

        Returns:
            VendorConfig instance

        Raises:
            VendorConfigError: If the file is invalid or missing required fields
            FileNotFoundError: If the file does not exist
        """
        path = Path(pyproject_path)
        if not path.exists():
            raise FileNotFoundError(f"pyproject.toml not found: {path}")

        try:
            with open(path, "rb") as f:
                pyproject = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise VendorConfigError(f"Invalid TOML syntax: {e}") from e

        return cls.from_pyproject_dict(pyproject, extra_exclude=extra_exclude)

    @classmethod
    def from_pyproject_dict(
        cls,
        pyproject: dict[str, Any],
        *,
        extra_exclude: list[str] | None = None,
    ) -> "VendorConfig":
        """Create VendorConfig from a parsed pyproject.toml dictionary.

        Args:
            pyproject: Parsed pyproject.toml as a dictionary
            extra_exclude: Additional packages to exclude from vendoring

        Returns:
            VendorConfig instance

        Raises:
            VendorConfigError: If required fields are missing
        """
        project = pyproject.get("project", {})
        tool_apworld = pyproject.get("tool", {}).get("apworld", {})
        vendor_config = tool_apworld.get("vendor", {})

        # Get package name from project.name
        package_name = project.get("name")
        if not package_name:
            raise VendorConfigError("Missing required field: 'name' in [project] section")

        # Get dependencies from project.dependencies
        dependencies = project.get("dependencies", [])

        # Get exclude list from tool.apworld.vendor.exclude
        exclude = list(vendor_config.get("exclude", []))
        if extra_exclude:
            exclude.extend(extra_exclude)

        # Get custom namespace if specified
        namespace = vendor_config.get("namespace", "_vendor")

        return cls(
            package_name=package_name,
            dependencies=dependencies,
            exclude=exclude,
            namespace=namespace,
        )


@dataclass
class VendoredPackage:
    """Information about a vendored package.

    Attributes:
        name: Package name (normalized)
        version: Package version
        source_path: Path where the package was extracted
        top_level_modules: List of top-level module names provided by this package
    """

    name: str
    version: str
    source_path: Path
    top_level_modules: list[str] = field(default_factory=list)


@dataclass
class VendorResult:
    """Result of a vendoring operation.

    Attributes:
        packages: List of vendored packages
        target_dir: Directory where packages were vendored
        errors: List of error messages for packages that failed to vendor
    """

    packages: list[VendoredPackage] = field(default_factory=list)
    target_dir: Path | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if vendoring was successful (no errors)."""
        return len(self.errors) == 0

    def get_vendored_module_names(self) -> set[str]:
        """Get all top-level module names from vendored packages.

        Returns:
            Set of module names that were vendored
        """
        modules: set[str] = set()
        for pkg in self.packages:
            modules.update(pkg.top_level_modules)
        return modules
