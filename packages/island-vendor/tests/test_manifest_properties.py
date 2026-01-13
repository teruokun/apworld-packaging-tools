# SPDX-License-Identifier: MIT
"""Property-based tests for vendor manifest completeness.

Feature: robust-vendoring
Property 6: Vendor Manifest Completeness
Validates: Requirements 3.1, 3.2, 3.3

These tests verify that:
- The manifest contains a dependency graph mapping each package to its direct dependencies
- The manifest contains platform tags for each vendored package
- The manifest contains an is_pure_python field reflecting the overall purity
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st, HealthCheck

from island_vendor.config import VendoredPackage, VendorResult
from island_vendor.packager import create_vendor_manifest
from island_vendor.platform import PlatformTag
from island_vendor.resolver import DependencyGraph, ResolvedDependency


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Pre-defined package names for faster generation
PACKAGE_NAMES = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
]

# Pre-defined module names
MODULE_NAMES = [
    "mod_a",
    "mod_b",
    "mod_c",
    "mod_d",
    "mod_e",
]

# Pre-defined versions
VERSIONS = ["1.0.0", "2.0.0", "3.0.0", "1.2.3", "0.1.0"]

# Platform tag strings
PLATFORM_TAG_STRINGS = [
    "py3-none-any",
    "cp311-cp311-linux_x86_64",
    "cp311-cp311-macosx_11_0_arm64",
    "cp311-cp311-win_amd64",
]


@st.composite
def dependency_graph_strategy(draw, min_packages: int = 1, max_packages: int = 3):
    """Generate a DependencyGraph with random packages and dependencies."""
    num_packages = draw(st.integers(min_value=min_packages, max_value=max_packages))

    # Use pre-defined names for speed
    pkg_names = PACKAGE_NAMES[:num_packages]

    graph = DependencyGraph()

    # Create packages with dependencies
    for i, name in enumerate(pkg_names):
        version = draw(st.sampled_from(VERSIONS))
        is_pure = draw(st.booleans())

        if is_pure:
            tags = ["py3-none-any"]
        else:
            tags = [draw(st.sampled_from(PLATFORM_TAG_STRINGS[1:]))]

        # Dependencies can only be packages that come after this one (to avoid cycles)
        possible_deps = pkg_names[i + 1 :]
        if possible_deps:
            num_deps = draw(st.integers(min_value=0, max_value=min(1, len(possible_deps))))
            deps = possible_deps[:num_deps]
        else:
            deps = []

        pkg = ResolvedDependency(
            name=name,
            version=version,
            requires=deps,
            platform_tags=tags,
            is_pure_python=is_pure,
        )
        graph.add_package(pkg)

    # Set root dependencies
    if pkg_names:
        graph.root_dependencies = [pkg_names[0]]

    return graph


@st.composite
def vendor_result_with_graph_strategy(draw):
    """Generate a VendorResult with a dependency graph."""
    graph = draw(dependency_graph_strategy())

    # Create VendoredPackage entries for each package in the graph
    packages = []
    for i, (name, resolved) in enumerate(graph.packages.items()):
        module = MODULE_NAMES[i % len(MODULE_NAMES)]
        pkg = VendoredPackage(
            name=name,
            version=resolved.version,
            source_path=Path("/tmp/vendor"),
            top_level_modules=[module],
        )
        packages.append(pkg)

    # Determine overall purity and platform tag
    is_pure = graph.is_pure_python()
    platform_tag = graph.get_most_restrictive_tag() if not is_pure else PlatformTag.pure_python()

    return VendorResult(
        packages=packages,
        target_dir=Path("/tmp/vendor"),
        errors=[],
        dependency_graph=graph,
        is_pure_python=is_pure,
        platform_tag=platform_tag,
    )


@st.composite
def vendor_result_without_graph_strategy(draw):
    """Generate a VendorResult without a dependency graph (legacy mode)."""
    num_packages = draw(st.integers(min_value=1, max_value=3))

    packages = []
    for i in range(num_packages):
        name = PACKAGE_NAMES[i]
        version = draw(st.sampled_from(VERSIONS))
        module = MODULE_NAMES[i % len(MODULE_NAMES)]
        pkg = VendoredPackage(
            name=name,
            version=version,
            source_path=Path("/tmp/vendor"),
            top_level_modules=[module],
        )
        packages.append(pkg)

    return VendorResult(
        packages=packages,
        target_dir=Path("/tmp/vendor"),
        errors=[],
        dependency_graph=None,
        is_pure_python=True,
        platform_tag=None,
    )


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestVendorManifestCompleteness:
    """Property-based tests for vendor manifest completeness.

    Feature: robust-vendoring, Property 6: Vendor Manifest Completeness
    Validates: Requirements 3.1, 3.2, 3.3
    """

    @given(result=vendor_result_with_graph_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_manifest_contains_dependency_graph(self, result: VendorResult):
        """
        Property 6: Vendor Manifest Completeness - Dependency Graph

        *For any* completed vendoring operation with a dependency graph,
        the manifest SHALL contain a dependency_graph mapping each package
        to its direct dependencies.

        **Validates: Requirements 3.1**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            manifest = json.loads(manifest_path.read_text())

            # Manifest must contain dependency_graph
            assert "dependency_graph" in manifest, "Manifest must contain dependency_graph"

            # dependency_graph must be a dict
            assert isinstance(
                manifest["dependency_graph"], dict
            ), "dependency_graph must be a dictionary"

            # Each package in the graph should be in dependency_graph
            if result.dependency_graph:
                for pkg_name in result.dependency_graph.packages:
                    assert (
                        pkg_name in manifest["dependency_graph"]
                    ), f"Package {pkg_name} should be in dependency_graph"

                    # The dependencies should match
                    expected_deps = result.dependency_graph.packages[pkg_name].requires
                    actual_deps = manifest["dependency_graph"][pkg_name]
                    assert actual_deps == expected_deps, f"Dependencies for {pkg_name} should match"

    @given(result=vendor_result_with_graph_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_manifest_contains_platform_tags_for_each_package(self, result: VendorResult):
        """
        Property 6: Vendor Manifest Completeness - Platform Tags

        *For any* completed vendoring operation, the manifest SHALL contain
        platform_tags for each vendored package.

        **Validates: Requirements 3.2**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            manifest = json.loads(manifest_path.read_text())

            # Each vendored package must have platform_tags
            assert "vendored_packages" in manifest

            for pkg_name, pkg_info in manifest["vendored_packages"].items():
                assert (
                    "platform_tags" in pkg_info
                ), f"Package {pkg_name} must have platform_tags field"
                assert isinstance(
                    pkg_info["platform_tags"], list
                ), f"platform_tags for {pkg_name} must be a list"

    @given(result=vendor_result_with_graph_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_manifest_contains_is_pure_python_field(self, result: VendorResult):
        """
        Property 6: Vendor Manifest Completeness - Pure Python Field

        *For any* completed vendoring operation, the manifest SHALL contain
        an is_pure_python field reflecting the overall purity.

        **Validates: Requirements 3.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            manifest = json.loads(manifest_path.read_text())

            # Manifest must contain is_pure_python
            assert "is_pure_python" in manifest, "Manifest must contain is_pure_python field"

            # is_pure_python must be a boolean
            assert isinstance(manifest["is_pure_python"], bool), "is_pure_python must be a boolean"

            # The value should match the VendorResult
            assert (
                manifest["is_pure_python"] == result.is_pure_python
            ), f"is_pure_python should be {result.is_pure_python}"

    @given(result=vendor_result_with_graph_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_manifest_contains_effective_platform_tag(self, result: VendorResult):
        """
        Property 6: Vendor Manifest Completeness - Effective Platform Tag

        *For any* completed vendoring operation, the manifest SHALL contain
        an effective_platform_tag field.

        **Validates: Requirements 3.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            manifest = json.loads(manifest_path.read_text())

            # Manifest must contain effective_platform_tag
            assert (
                "effective_platform_tag" in manifest
            ), "Manifest must contain effective_platform_tag field"

            # If result has a platform_tag, it should be in the manifest
            if result.platform_tag:
                assert manifest["effective_platform_tag"] == str(
                    result.platform_tag
                ), f"effective_platform_tag should be {result.platform_tag}"

    @given(result=vendor_result_with_graph_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_manifest_contains_root_dependencies(self, result: VendorResult):
        """
        Property 6: Vendor Manifest Completeness - Root Dependencies

        *For any* completed vendoring operation with a dependency graph,
        the manifest SHALL contain root_dependencies listing the direct
        dependencies from the project.

        **Validates: Requirements 3.1**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            manifest = json.loads(manifest_path.read_text())

            # Manifest must contain root_dependencies
            assert "root_dependencies" in manifest, "Manifest must contain root_dependencies field"

            # root_dependencies must be a list
            assert isinstance(
                manifest["root_dependencies"], list
            ), "root_dependencies must be a list"

            # If we have a dependency graph, root_dependencies should match
            if result.dependency_graph:
                expected_roots = result.dependency_graph.root_dependencies
                assert (
                    manifest["root_dependencies"] == expected_roots
                ), f"root_dependencies should be {expected_roots}"

    @given(result=vendor_result_with_graph_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_manifest_packages_have_is_pure_python(self, result: VendorResult):
        """
        Property 6: Vendor Manifest Completeness - Per-Package Purity

        *For any* completed vendoring operation, each package in the manifest
        SHALL have an is_pure_python field.

        **Validates: Requirements 3.2, 3.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            manifest = json.loads(manifest_path.read_text())

            # Each vendored package must have is_pure_python
            for pkg_name, pkg_info in manifest["vendored_packages"].items():
                assert (
                    "is_pure_python" in pkg_info
                ), f"Package {pkg_name} must have is_pure_python field"
                assert isinstance(
                    pkg_info["is_pure_python"], bool
                ), f"is_pure_python for {pkg_name} must be a boolean"

    @given(result=vendor_result_with_graph_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_manifest_packages_have_direct_dependencies(self, result: VendorResult):
        """
        Property 6: Vendor Manifest Completeness - Direct Dependencies

        *For any* completed vendoring operation, each package in the manifest
        SHALL have a direct_dependencies field.

        **Validates: Requirements 3.1**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            manifest = json.loads(manifest_path.read_text())

            # Each vendored package must have direct_dependencies
            for pkg_name, pkg_info in manifest["vendored_packages"].items():
                assert (
                    "direct_dependencies" in pkg_info
                ), f"Package {pkg_name} must have direct_dependencies field"
                assert isinstance(
                    pkg_info["direct_dependencies"], list
                ), f"direct_dependencies for {pkg_name} must be a list"

    @given(result=vendor_result_without_graph_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_manifest_works_without_dependency_graph(self, result: VendorResult):
        """
        Property 6: Vendor Manifest Completeness - Legacy Mode

        *For any* vendoring operation without a dependency graph (legacy mode),
        the manifest SHALL still be created with default values for new fields.

        **Validates: Requirements 3.1, 3.2, 3.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            manifest = json.loads(manifest_path.read_text())

            # All required fields should be present
            assert "vendored_packages" in manifest
            assert "dependency_graph" in manifest
            assert "root_dependencies" in manifest
            assert "is_pure_python" in manifest
            assert "effective_platform_tag" in manifest

            # Each package should have all required fields
            for pkg_name, pkg_info in manifest["vendored_packages"].items():
                assert "version" in pkg_info
                assert "modules" in pkg_info
                assert "is_pure_python" in pkg_info
                assert "platform_tags" in pkg_info
                assert "direct_dependencies" in pkg_info

    @given(result=vendor_result_with_graph_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_manifest_is_valid_json(self, result: VendorResult):
        """
        Property 6: Vendor Manifest Completeness - Valid JSON

        *For any* completed vendoring operation, the manifest SHALL be
        valid JSON that can be parsed.

        **Validates: Requirements 3.1, 3.2, 3.3**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            # Should not raise an exception
            content = manifest_path.read_text()
            manifest = json.loads(content)

            # Should be a dict
            assert isinstance(manifest, dict)

    @given(
        graph=dependency_graph_strategy(min_packages=2, max_packages=3),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example],
    )
    def test_manifest_preserves_dependency_relationships(self, graph: DependencyGraph):
        """
        Property 6: Vendor Manifest Completeness - Relationship Preservation

        *For any* dependency graph with relationships A -> B,
        the manifest SHALL preserve that A depends on B.

        **Validates: Requirements 3.1**
        """
        # Create VendoredPackage entries
        packages = []
        for i, (name, resolved) in enumerate(graph.packages.items()):
            module = MODULE_NAMES[i % len(MODULE_NAMES)]
            pkg = VendoredPackage(
                name=name,
                version=resolved.version,
                source_path=Path("/tmp/vendor"),
                top_level_modules=[module],
            )
            packages.append(pkg)

        result = VendorResult(
            packages=packages,
            target_dir=Path("/tmp/vendor"),
            errors=[],
            dependency_graph=graph,
            is_pure_python=graph.is_pure_python(),
            platform_tag=graph.get_most_restrictive_tag(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "vendor_manifest.json"
            create_vendor_manifest(result, manifest_path)

            manifest = json.loads(manifest_path.read_text())

            # Verify all dependency relationships are preserved
            for pkg_name, resolved in graph.packages.items():
                if pkg_name in manifest["dependency_graph"]:
                    manifest_deps = set(manifest["dependency_graph"][pkg_name])
                    expected_deps = set(resolved.requires)
                    assert (
                        manifest_deps == expected_deps
                    ), f"Dependencies for {pkg_name} should be preserved"
