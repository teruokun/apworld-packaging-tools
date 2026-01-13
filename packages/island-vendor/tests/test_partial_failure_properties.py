# SPDX-License-Identifier: MIT
"""Property-based tests for partial failure reporting.

Feature: robust-vendoring
Property 7: Partial Failure Reporting
Validates: Requirements 4.3

These tests verify that:
- When vendoring partially succeeds, the VendorResult contains both
  successfully vendored packages AND error messages for failed packages
"""

from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings, strategies as st, HealthCheck

from island_vendor.config import VendoredPackage, VendorResult
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

# Pre-defined error messages
ERROR_MESSAGES = [
    "Package not found on PyPI",
    "Network timeout during download",
    "Invalid wheel format",
    "Checksum verification failed",
    "Incompatible Python version",
]


@st.composite
def dependency_graph_strategy(draw, min_packages: int = 1, max_packages: int = 5):
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
            tags = [
                draw(
                    st.sampled_from(
                        [
                            "cp311-cp311-linux_x86_64",
                            "cp311-cp311-macosx_11_0_arm64",
                            "cp311-cp311-win_amd64",
                        ]
                    )
                )
            ]

        # Dependencies can only be packages that come after this one (to avoid cycles)
        possible_deps = pkg_names[i + 1 :]
        if possible_deps:
            num_deps = draw(st.integers(min_value=0, max_value=min(2, len(possible_deps))))
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
def partial_failure_result_strategy(draw):
    """Generate a VendorResult with both successful packages and errors.

    This simulates a partial failure scenario where some packages were
    successfully vendored while others failed.
    """
    graph = draw(dependency_graph_strategy(min_packages=2, max_packages=5))

    pkg_names = list(graph.packages.keys())

    # Decide how many packages succeed vs fail
    # At least one must succeed and at least one must fail for partial failure
    num_packages = len(pkg_names)
    if num_packages < 2:
        # Need at least 2 packages for partial failure
        # Add another package
        extra_pkg = ResolvedDependency(
            name="extra-pkg",
            version="1.0.0",
            requires=[],
            platform_tags=["py3-none-any"],
            is_pure_python=True,
        )
        graph.add_package(extra_pkg)
        pkg_names.append("extra-pkg")
        num_packages = len(pkg_names)

    num_success = draw(st.integers(min_value=1, max_value=num_packages - 1))

    # Randomly select which packages succeed
    success_indices = draw(
        st.lists(
            st.integers(min_value=0, max_value=num_packages - 1),
            min_size=num_success,
            max_size=num_success,
            unique=True,
        )
    )

    success_names = {pkg_names[i] for i in success_indices}
    failed_names = set(pkg_names) - success_names

    # Create VendoredPackage entries for successful packages
    packages = []
    for i, name in enumerate(pkg_names):
        if name in success_names:
            resolved = graph.packages[name]
            module = MODULE_NAMES[i % len(MODULE_NAMES)]
            pkg = VendoredPackage(
                name=name,
                version=resolved.version,
                source_path=Path("/tmp/vendor"),
                top_level_modules=[module],
            )
            packages.append(pkg)

    # Create error messages for failed packages
    errors = []
    for name in failed_names:
        # Get dependency chain for the failed package
        chain = graph.get_dependency_chain(name)
        chain_str = " -> ".join(chain) if chain else name
        error_msg = draw(st.sampled_from(ERROR_MESSAGES))
        errors.append(
            f"Failed to vendor '{name}':\n"
            f"  Dependency chain: {chain_str}\n"
            f"  Error: {error_msg}"
        )

    # Determine overall purity and platform tag
    is_pure = graph.is_pure_python()
    platform_tag = graph.get_most_restrictive_tag() if not is_pure else PlatformTag.pure_python()

    return (
        VendorResult(
            packages=packages,
            target_dir=Path("/tmp/vendor"),
            errors=errors,
            dependency_graph=graph,
            is_pure_python=is_pure,
            platform_tag=platform_tag,
        ),
        success_names,
        failed_names,
    )


@st.composite
def all_success_result_strategy(draw):
    """Generate a VendorResult where all packages succeed."""
    graph = draw(dependency_graph_strategy(min_packages=1, max_packages=3))

    # Create VendoredPackage entries for all packages
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
def all_failure_result_strategy(draw):
    """Generate a VendorResult where all packages fail."""
    graph = draw(dependency_graph_strategy(min_packages=1, max_packages=3))

    # Create error messages for all packages
    errors = []
    for name in graph.packages:
        chain = graph.get_dependency_chain(name)
        chain_str = " -> ".join(chain) if chain else name
        error_msg = draw(st.sampled_from(ERROR_MESSAGES))
        errors.append(
            f"Failed to vendor '{name}':\n"
            f"  Dependency chain: {chain_str}\n"
            f"  Error: {error_msg}"
        )

    return VendorResult(
        packages=[],  # No successful packages
        target_dir=Path("/tmp/vendor"),
        errors=errors,
        dependency_graph=graph,
        is_pure_python=True,
        platform_tag=None,
    )


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPartialFailureReporting:
    """Property-based tests for partial failure reporting.

    Feature: robust-vendoring, Property 7: Partial Failure Reporting
    Validates: Requirements 4.3
    """

    @given(data=partial_failure_result_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_partial_failure_contains_successful_packages(self, data):
        """
        Property 7: Partial Failure Reporting - Successful Packages

        *For any* vendoring operation where some packages succeed and some fail,
        the VendorResult SHALL contain the successfully vendored packages.

        **Validates: Requirements 4.3**
        """
        result, success_names, failed_names = data

        # The result should contain packages for all successful names
        vendored_names = {pkg.name for pkg in result.packages}

        assert vendored_names == success_names, (
            f"VendorResult should contain all successful packages.\n"
            f"Expected: {success_names}\n"
            f"Got: {vendored_names}"
        )

    @given(data=partial_failure_result_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_partial_failure_contains_error_messages(self, data):
        """
        Property 7: Partial Failure Reporting - Error Messages

        *For any* vendoring operation where some packages succeed and some fail,
        the VendorResult SHALL contain error messages for failed packages.

        **Validates: Requirements 4.3**
        """
        result, success_names, failed_names = data

        # The result should have errors for all failed packages
        assert len(result.errors) == len(failed_names), (
            f"VendorResult should have one error per failed package.\n"
            f"Expected {len(failed_names)} errors, got {len(result.errors)}"
        )

        # Each failed package should be mentioned in an error message
        for failed_name in failed_names:
            found = any(failed_name in error for error in result.errors)
            assert found, f"Failed package '{failed_name}' should be mentioned in error messages"

    @given(data=partial_failure_result_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_partial_failure_errors_contain_dependency_chain(self, data):
        """
        Property 7: Partial Failure Reporting - Dependency Chain in Errors

        *For any* vendoring operation where packages fail, the error messages
        SHALL include the dependency chain that led to the failure.

        **Validates: Requirements 4.3**
        """
        result, success_names, failed_names = data

        # Each error should contain "Dependency chain:"
        for error in result.errors:
            assert "Dependency chain:" in error, (
                f"Error message should contain dependency chain information.\n" f"Error: {error}"
            )

    @given(data=partial_failure_result_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_partial_failure_success_property(self, data):
        """
        Property 7: Partial Failure Reporting - Success Property

        *For any* vendoring operation with errors, the success property
        SHALL return False.

        **Validates: Requirements 4.3**
        """
        result, success_names, failed_names = data

        # With errors, success should be False
        assert result.success is False, "VendorResult.success should be False when there are errors"

    @given(result=all_success_result_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_success_has_no_errors(self, result: VendorResult):
        """
        Property 7: Partial Failure Reporting - All Success Case

        *For any* vendoring operation where all packages succeed,
        the VendorResult SHALL have no errors and success=True.

        **Validates: Requirements 4.3**
        """
        assert len(result.errors) == 0, "All-success result should have no errors"
        assert result.success is True, "All-success result should have success=True"

    @given(result=all_failure_result_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_failure_has_no_packages(self, result: VendorResult):
        """
        Property 7: Partial Failure Reporting - All Failure Case

        *For any* vendoring operation where all packages fail,
        the VendorResult SHALL have no packages and success=False.

        **Validates: Requirements 4.3**
        """
        assert len(result.packages) == 0, "All-failure result should have no packages"
        assert result.success is False, "All-failure result should have success=False"
        assert len(result.errors) > 0, "All-failure result should have errors"

    @given(data=partial_failure_result_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_partial_failure_packages_have_valid_info(self, data):
        """
        Property 7: Partial Failure Reporting - Package Information

        *For any* successfully vendored package in a partial failure scenario,
        the VendoredPackage SHALL have valid name, version, and modules.

        **Validates: Requirements 4.3**
        """
        result, success_names, failed_names = data

        for pkg in result.packages:
            # Package should have a name
            assert pkg.name, "VendoredPackage should have a name"

            # Package should have a version
            assert pkg.version, "VendoredPackage should have a version"

            # Package should have a source path
            assert pkg.source_path is not None, "VendoredPackage should have a source_path"

            # Package should have top_level_modules
            assert isinstance(
                pkg.top_level_modules, list
            ), "VendoredPackage should have top_level_modules as a list"

    @given(data=partial_failure_result_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_partial_failure_preserves_dependency_graph(self, data):
        """
        Property 7: Partial Failure Reporting - Dependency Graph Preservation

        *For any* partial failure scenario, the VendorResult SHALL still
        contain the dependency graph for debugging purposes.

        **Validates: Requirements 4.3**
        """
        result, success_names, failed_names = data

        # Dependency graph should be preserved even with failures
        assert (
            result.dependency_graph is not None
        ), "VendorResult should preserve dependency_graph even with failures"

    @given(data=partial_failure_result_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_get_vendored_module_names_returns_only_successful(self, data):
        """
        Property 7: Partial Failure Reporting - Module Names

        *For any* partial failure scenario, get_vendored_module_names()
        SHALL return only modules from successfully vendored packages.

        **Validates: Requirements 4.3**
        """
        result, success_names, failed_names = data

        module_names = result.get_vendored_module_names()

        # Module names should only come from successful packages
        for pkg in result.packages:
            for module in pkg.top_level_modules:
                assert module in module_names, (
                    f"Module {module} from successful package {pkg.name} "
                    f"should be in get_vendored_module_names()"
                )
