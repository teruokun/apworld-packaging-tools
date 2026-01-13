# SPDX-License-Identifier: MIT
"""Dependency resolution with transitive dependency support.

This module provides components for resolving Python dependencies including
their transitive dependencies, while respecting exclusion rules for Core AP
modules and the archipelago-core package tree.
"""

from __future__ import annotations

import email.parser
import re
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .platform import PlatformTag


@dataclass
class ResolvedDependency:
    """A resolved dependency with its metadata.

    Attributes:
        name: Normalized package name
        version: Package version string
        requires: List of direct dependencies (package names) of this package
        platform_tags: Platform tags from wheel filename
        is_pure_python: True if package has no native extensions (py3-none-any)
        wheel_path: Path to the downloaded wheel file, if available
    """

    name: str
    version: str
    requires: list[str] = field(default_factory=list)
    platform_tags: list[str] = field(default_factory=list)
    is_pure_python: bool = True
    wheel_path: Path | None = None


@dataclass
class DependencyGraph:
    """Graph of resolved dependencies."""

    packages: dict[str, ResolvedDependency] = field(default_factory=dict)
    root_dependencies: list[str] = field(default_factory=list)

    def get_transitive_closure(self, package: str) -> set[str]:
        """Get all transitive dependencies of a package."""
        visited: set[str] = set()
        self._collect_transitive(package, visited)
        visited.discard(package)
        return visited

    def _collect_transitive(self, package: str, visited: set[str]) -> None:
        """Recursively collect transitive dependencies."""
        if package in visited:
            return
        visited.add(package)
        resolved = self.packages.get(package)
        if resolved:
            for dep in resolved.requires:
                self._collect_transitive(dep, visited)

    def get_all_packages(self) -> list[ResolvedDependency]:
        """Get all packages in topological order."""
        in_degree: dict[str, int] = {name: 0 for name in self.packages}
        for pkg in self.packages.values():
            for dep in pkg.requires:
                if dep in in_degree:
                    in_degree[dep] += 1

        queue = [pkg_name for pkg_name, degree in in_degree.items() if degree == 0]
        result: list[ResolvedDependency] = []

        while queue:
            current_name = queue.pop(0)
            current_pkg = self.packages.get(current_name)
            if current_pkg is not None:
                result.append(current_pkg)
                for dep in current_pkg.requires:
                    if dep in in_degree:
                        in_degree[dep] -= 1
                        if in_degree[dep] == 0:
                            queue.append(dep)

        for remaining_pkg in self.packages.values():
            if remaining_pkg not in result:
                result.append(remaining_pkg)

        return result

    def is_pure_python(self) -> bool:
        """Check if all packages in the graph are pure Python."""
        return all(pkg.is_pure_python for pkg in self.packages.values())

    def get_platform_specific_packages(self) -> list[ResolvedDependency]:
        """Get all packages that are platform-specific."""
        return [pkg for pkg in self.packages.values() if not pkg.is_pure_python]

    def get_most_restrictive_tag(self) -> PlatformTag:
        """Get the most restrictive platform tag from all packages.

        If all packages are pure Python, returns py3-none-any.
        Otherwise, returns the most specific platform tag.

        Returns:
            The most restrictive PlatformTag
        """
        from .platform import PlatformTag, compute_most_restrictive_tag

        all_tags: list[PlatformTag] = []

        for pkg in self.packages.values():
            for tag_str in pkg.platform_tags:
                try:
                    tag = PlatformTag.from_string(tag_str)
                    all_tags.append(tag)
                except ValueError:
                    continue

        return compute_most_restrictive_tag(all_tags)

    def add_package(self, package: ResolvedDependency) -> None:
        """Add a package to the graph."""
        self.packages[package.name] = package

    def has_package(self, name: str) -> bool:
        """Check if a package exists in the graph."""
        return name in self.packages

    def get_package(self, name: str) -> ResolvedDependency | None:
        """Get a package by name."""
        return self.packages.get(name)

    def filter_packages(self, exclude: set[str]) -> DependencyGraph:
        """Create a new graph with excluded packages removed.

        Args:
            exclude: Set of normalized package names to exclude

        Returns:
            New DependencyGraph with excluded packages removed
        """
        filtered = DependencyGraph()
        filtered.root_dependencies = [dep for dep in self.root_dependencies if dep not in exclude]

        for name, pkg in self.packages.items():
            if name not in exclude:
                # Create a copy with filtered requires
                filtered_requires = [r for r in pkg.requires if r not in exclude]
                filtered_pkg = ResolvedDependency(
                    name=pkg.name,
                    version=pkg.version,
                    requires=filtered_requires,
                    platform_tags=pkg.platform_tags.copy(),
                    is_pure_python=pkg.is_pure_python,
                    wheel_path=pkg.wheel_path,
                )
                filtered.add_package(filtered_pkg)

        return filtered

    def get_dependency_chain(self, target: str) -> list[str]:
        """Get the dependency chain from a root dependency to a target package.

        Uses BFS to find the shortest path from any root dependency to the target.

        Args:
            target: The target package name to find a chain to

        Returns:
            List of package names representing the chain from root to target,
            or an empty list if no chain exists
        """
        if target in self.root_dependencies:
            return [target]

        # BFS to find shortest path
        from collections import deque

        # Build reverse graph (child -> parents)
        reverse_graph: dict[str, list[str]] = {name: [] for name in self.packages}
        for name, pkg in self.packages.items():
            for dep in pkg.requires:
                if dep in reverse_graph:
                    reverse_graph[dep].append(name)

        # BFS from target back to roots
        queue: deque[tuple[str, list[str]]] = deque([(target, [target])])
        visited: set[str] = {target}

        while queue:
            current, path = queue.popleft()

            # Check if we reached a root
            if current in self.root_dependencies:
                return list(reversed(path))

            # Explore parents
            for parent in reverse_graph.get(current, []):
                if parent not in visited:
                    visited.add(parent)
                    queue.append((parent, path + [parent]))

        return [target]  # No chain found, return just the target


class DependencyResolverError(Exception):
    """Raised when dependency resolution fails."""

    pass


class DependencyChainError(DependencyResolverError):
    """Raised when a dependency fails with chain information.

    This exception includes the dependency chain that led to the failure,
    making it easier to diagnose which transitive dependency caused the issue.

    Attributes:
        package: The package that failed
        chain: The dependency chain leading to the failed package
        original_error: The original error message
    """

    def __init__(
        self,
        package: str,
        chain: list[str],
        original_error: str,
    ):
        self.package = package
        self.chain = chain
        self.original_error = original_error
        chain_str = " -> ".join(chain) if chain else package
        super().__init__(
            f"Failed to resolve '{package}':\n"
            f"  Dependency chain: {chain_str}\n"
            f"  Error: {original_error}"
        )


def _normalize_package_name(name: str) -> str:
    """Normalize a package name for comparison."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_requirement_name(requirement: str) -> str:
    """Extract package name from a requirement string."""
    match = re.match(r"^([a-zA-Z0-9][-a-zA-Z0-9._]*)", requirement)
    if match:
        return _normalize_package_name(match.group(1))
    return _normalize_package_name(requirement)


def _parse_requires_dist(requires_dist: list[str]) -> list[str]:
    """Parse Requires-Dist entries and return package names."""
    result = []
    for req in requires_dist:
        parts = req.split(";", 1)
        pkg_part = parts[0].strip()
        if len(parts) > 1:
            marker = parts[1].strip()
            if "extra" in marker.lower():
                continue
        pkg_name = _parse_requirement_name(pkg_part)
        if pkg_name:
            result.append(pkg_name)
    return result


def _parse_wheel_tags(wheel_filename: str) -> tuple[list[str], bool]:
    """Parse platform tags from a wheel filename."""
    name = wheel_filename.rsplit(".", 1)[0]
    parts = name.split("-")
    if len(parts) < 5:
        return ["py3-none-any"], True
    python_tag = parts[-3]
    abi_tag = parts[-2]
    platform_tag = parts[-1]
    full_tag = f"{python_tag}-{abi_tag}-{platform_tag}"
    is_pure = platform_tag == "any" and abi_tag == "none"
    return [full_tag], is_pure


class DependencyResolver:
    """Resolves dependencies including transitive ones."""

    def __init__(
        self,
        exclude_packages: set[str] | None = None,
        core_ap_modules: frozenset[str] | None = None,
        archipelago_core_name: str = "archipelago-core",
    ):
        """Initialize the dependency resolver."""
        from .config import CORE_AP_MODULES

        self.exclude_packages = {_normalize_package_name(p) for p in (exclude_packages or set())}
        self.core_ap_modules = core_ap_modules or CORE_AP_MODULES
        self.archipelago_core_name = _normalize_package_name(archipelago_core_name)
        self._archipelago_core_deps: set[str] | None = None

    def resolve(
        self,
        requirements: list[str],
        python_executable: str | None = None,
    ) -> DependencyGraph:
        """Resolve all dependencies including transitive ones."""
        if not requirements:
            return DependencyGraph()

        python = python_executable or sys.executable
        graph = DependencyGraph()
        graph.root_dependencies = [_parse_requirement_name(r) for r in requirements]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            wheel_dir = temp_path / "wheels"
            wheel_dir.mkdir()

            cmd = [
                python,
                "-m",
                "pip",
                "download",
                "--dest",
                str(wheel_dir),
                "--only-binary=:all:",
                "--quiet",
            ]
            cmd.extend(requirements)

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    raise DependencyResolverError(
                        f"pip download failed:\n{result.stderr}\n{result.stdout}"
                    )
            except FileNotFoundError:
                raise DependencyResolverError(f"Python executable not found: {python}") from None
            except Exception as e:
                raise DependencyResolverError(f"Failed to run pip: {e}") from e

            for wheel_file in wheel_dir.glob("*.whl"):
                resolved = self._parse_wheel(wheel_file)
                if resolved:
                    graph.add_package(resolved)

        return graph

    def _parse_wheel(self, wheel_path: Path) -> ResolvedDependency | None:
        """Parse a wheel file to extract dependency information."""
        try:
            with zipfile.ZipFile(wheel_path, "r") as whl:
                metadata_path = None
                for name in whl.namelist():
                    if name.endswith("/METADATA"):
                        metadata_path = name
                        break

                if not metadata_path:
                    return None

                metadata_content = whl.read(metadata_path).decode("utf-8")
                parser = email.parser.Parser()
                metadata = parser.parsestr(metadata_content)

                name = metadata.get("Name", "")
                version = metadata.get("Version", "unknown")
                requires_dist = metadata.get_all("Requires-Dist") or []

                if not name:
                    return None

                normalized_name = _normalize_package_name(name)
                requires = _parse_requires_dist(requires_dist)
                platform_tags, is_pure = _parse_wheel_tags(wheel_path.name)

                return ResolvedDependency(
                    name=normalized_name,
                    version=version,
                    requires=requires,
                    platform_tags=platform_tags,
                    is_pure_python=is_pure,
                    wheel_path=wheel_path,
                )
        except Exception:
            return None

    def get_archipelago_core_deps(self, python_executable: str | None = None) -> set[str]:
        """Get the transitive dependency tree of archipelago-core."""
        if self._archipelago_core_deps is not None:
            return self._archipelago_core_deps

        try:
            graph = self.resolve([self.archipelago_core_name], python_executable)
            self._archipelago_core_deps = set(graph.packages.keys())
        except DependencyResolverError:
            self._archipelago_core_deps = set()

        return self._archipelago_core_deps

    def should_include(self, package_name: str) -> bool:
        """Check if a package should be included in the resolution."""
        normalized = _normalize_package_name(package_name)

        if normalized in self.exclude_packages:
            return False

        if package_name in self.core_ap_modules:
            return False

        if normalized == self.archipelago_core_name:
            return False

        return True

    def get_all_exclusions(self, python_executable: str | None = None) -> set[str]:
        """Get all packages that should be excluded.

        This includes:
        - Explicitly excluded packages
        - Core AP modules (normalized)
        - archipelago-core and its transitive dependencies

        Args:
            python_executable: Python executable to use for resolving
                archipelago-core dependencies

        Returns:
            Set of normalized package names to exclude
        """
        exclusions: set[str] = set()

        # Add explicitly excluded packages
        exclusions.update(self.exclude_packages)

        # Add normalized Core AP modules
        exclusions.update(_normalize_package_name(m) for m in self.core_ap_modules)

        # Add archipelago-core itself
        exclusions.add(self.archipelago_core_name)

        # Add archipelago-core's transitive dependencies
        exclusions.update(self.get_archipelago_core_deps(python_executable))

        return exclusions

    def resolve_and_filter(
        self,
        requirements: list[str],
        python_executable: str | None = None,
    ) -> DependencyGraph:
        """Resolve dependencies and filter out excluded packages.

        This is a convenience method that combines resolve() with filtering
        based on exclusion rules.

        Args:
            requirements: List of pip requirement strings
            python_executable: Python executable to use

        Returns:
            DependencyGraph with excluded packages removed
        """
        # First resolve all dependencies
        graph = self.resolve(requirements, python_executable)

        # Get all exclusions
        exclusions = self.get_all_exclusions(python_executable)

        # Filter the graph
        return graph.filter_packages(exclusions)
