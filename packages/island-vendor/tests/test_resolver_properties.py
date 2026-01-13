# SPDX-License-Identifier: MIT
"""Property-based tests for dependency resolution.

Feature: robust-vendoring
Property 1: Transitive Dependency Completeness
Validates: Requirements 1.1, 1.4

These tests verify that:
- Transitive dependencies are correctly tracked in the dependency graph
- The dependency graph contains all packages reachable from root dependencies
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from island_vendor.resolver import (
    DependencyGraph,
    ResolvedDependency,
)


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Valid normalized package names (lowercase, hyphens)
valid_package_names = st.from_regex(r"[a-z][a-z0-9-]{0,15}", fullmatch=True)


@st.composite
def resolved_dependency(draw, name: str | None = None):
    """Generate a ResolvedDependency with optional specific name."""
    pkg_name = name if name else draw(valid_package_names)
    version = f"{draw(st.integers(0, 10))}.{draw(st.integers(0, 10))}.{draw(st.integers(0, 10))}"
    is_pure = draw(st.booleans())
    platform_tag = "py3-none-any" if is_pure else "cp311-cp311-linux_x86_64"

    return ResolvedDependency(
        name=pkg_name,
        version=version,
        requires=[],  # Will be set by dependency_graph strategy
        platform_tags=[platform_tag],
        is_pure_python=is_pure,
        wheel_path=None,
    )


@st.composite
def dependency_graph_with_chain(draw):
    """Generate a dependency graph with a chain A -> B -> C.

    This creates a graph where:
    - Package A depends on B
    - Package B depends on C
    - Package C has no dependencies

    This is useful for testing transitive dependency completeness.
    """
    # Generate three unique package names
    names = draw(st.lists(valid_package_names, min_size=3, max_size=3, unique=True))
    pkg_a_name, pkg_b_name, pkg_c_name = names

    # Create packages with dependency chain
    pkg_c = ResolvedDependency(
        name=pkg_c_name,
        version="1.0.0",
        requires=[],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    pkg_b = ResolvedDependency(
        name=pkg_b_name,
        version="1.0.0",
        requires=[pkg_c_name],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    pkg_a = ResolvedDependency(
        name=pkg_a_name,
        version="1.0.0",
        requires=[pkg_b_name],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    graph = DependencyGraph()
    graph.add_package(pkg_a)
    graph.add_package(pkg_b)
    graph.add_package(pkg_c)
    graph.root_dependencies = [pkg_a_name]

    return graph, pkg_a_name, pkg_b_name, pkg_c_name


@st.composite
def dependency_graph_with_diamond(draw):
    """Generate a dependency graph with diamond pattern A -> B, C -> D.

    This creates a graph where:
    - Package A depends on B and C
    - Package B depends on D
    - Package C depends on D
    - Package D has no dependencies

    This tests that shared transitive dependencies are handled correctly.
    """
    names = draw(st.lists(valid_package_names, min_size=4, max_size=4, unique=True))
    pkg_a_name, pkg_b_name, pkg_c_name, pkg_d_name = names

    pkg_d = ResolvedDependency(
        name=pkg_d_name,
        version="1.0.0",
        requires=[],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    pkg_b = ResolvedDependency(
        name=pkg_b_name,
        version="1.0.0",
        requires=[pkg_d_name],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    pkg_c = ResolvedDependency(
        name=pkg_c_name,
        version="1.0.0",
        requires=[pkg_d_name],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    pkg_a = ResolvedDependency(
        name=pkg_a_name,
        version="1.0.0",
        requires=[pkg_b_name, pkg_c_name],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    graph = DependencyGraph()
    graph.add_package(pkg_a)
    graph.add_package(pkg_b)
    graph.add_package(pkg_c)
    graph.add_package(pkg_d)
    graph.root_dependencies = [pkg_a_name]

    return graph, pkg_a_name, pkg_b_name, pkg_c_name, pkg_d_name


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestTransitiveDependencyCompleteness:
    """Property-based tests for transitive dependency completeness.

    Feature: robust-vendoring, Property 1: Transitive Dependency Completeness
    Validates: Requirements 1.1, 1.4
    """

    @given(data=dependency_graph_with_chain())
    @settings(max_examples=100)
    def test_chain_transitive_closure_contains_all_deps(self, data):
        """
        Property 1: Transitive Dependency Completeness - Chain

        *For any* dependency graph where package A depends on package B,
        and B depends on package C, the transitive closure of A SHALL
        contain both B and C.

        **Validates: Requirements 1.1, 1.4**
        """
        graph, pkg_a, pkg_b, pkg_c = data

        # Get transitive closure of A
        closure = graph.get_transitive_closure(pkg_a)

        # B and C should be in the closure
        assert pkg_b in closure, f"Direct dependency {pkg_b} not in closure"
        assert pkg_c in closure, f"Transitive dependency {pkg_c} not in closure"

        # A should NOT be in its own closure
        assert pkg_a not in closure, "Package should not be in its own closure"

    @given(data=dependency_graph_with_diamond())
    @settings(max_examples=100)
    def test_diamond_transitive_closure_contains_all_deps(self, data):
        """
        Property 1: Transitive Dependency Completeness - Diamond

        *For any* dependency graph with diamond pattern (A -> B,C -> D),
        the transitive closure of A SHALL contain B, C, and D exactly once.

        **Validates: Requirements 1.1, 1.4**
        """
        graph, pkg_a, pkg_b, pkg_c, pkg_d = data

        closure = graph.get_transitive_closure(pkg_a)

        # All dependencies should be in the closure
        assert pkg_b in closure, f"Direct dependency {pkg_b} not in closure"
        assert pkg_c in closure, f"Direct dependency {pkg_c} not in closure"
        assert pkg_d in closure, f"Shared transitive dependency {pkg_d} not in closure"

        # Closure should have exactly 3 elements (B, C, D)
        assert len(closure) == 3, f"Expected 3 deps, got {len(closure)}"

    @given(data=dependency_graph_with_chain())
    @settings(max_examples=100)
    def test_all_packages_returns_complete_set(self, data):
        """
        Property 1: Transitive Dependency Completeness - All Packages

        *For any* dependency graph, get_all_packages() SHALL return all
        packages in the graph including transitive dependencies.

        **Validates: Requirements 1.1, 1.4**
        """
        graph, pkg_a, pkg_b, pkg_c = data

        all_packages = graph.get_all_packages()
        all_names = {pkg.name for pkg in all_packages}

        # All packages should be present
        assert pkg_a in all_names
        assert pkg_b in all_names
        assert pkg_c in all_names
        assert len(all_packages) == 3

    @given(data=dependency_graph_with_chain())
    @settings(max_examples=100)
    def test_graph_has_all_root_dependencies(self, data):
        """
        Property 1: Transitive Dependency Completeness - Root Dependencies

        *For any* dependency graph, all root_dependencies SHALL be present
        in the packages dict.

        **Validates: Requirements 1.1, 1.4**
        """
        graph, pkg_a, _, _ = data

        # Root dependency should be in the graph
        assert graph.has_package(pkg_a)
        assert pkg_a in graph.root_dependencies

    @given(data=dependency_graph_with_chain())
    @settings(max_examples=100)
    def test_transitive_closure_subset_of_all_packages(self, data):
        """
        Property 1: Transitive Dependency Completeness - Subset Property

        *For any* package in a dependency graph, its transitive closure
        SHALL be a subset of all packages in the graph (excluding itself).

        **Validates: Requirements 1.1, 1.4**
        """
        graph, pkg_a, _, _ = data

        closure = graph.get_transitive_closure(pkg_a)
        all_names = {pkg.name for pkg in graph.get_all_packages()}

        # Closure should be a subset of all packages
        assert closure.issubset(all_names)

        # Package itself should not be in closure
        assert pkg_a not in closure


# =============================================================================
# Property 2: Exclusion Rules Consistency Tests
# =============================================================================


@st.composite
def dependency_graph_with_exclusions(draw):
    """Generate a dependency graph with some packages marked for exclusion.

    Creates a graph where:
    - Package A depends on B and C
    - Package B depends on D
    - Package C is in the exclude list
    - Package D is a Core AP module

    This tests that exclusion rules are applied consistently.
    """
    names = draw(st.lists(valid_package_names, min_size=4, max_size=4, unique=True))
    pkg_a_name, pkg_b_name, pkg_c_name, pkg_d_name = names

    pkg_d = ResolvedDependency(
        name=pkg_d_name,
        version="1.0.0",
        requires=[],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    pkg_c = ResolvedDependency(
        name=pkg_c_name,
        version="1.0.0",
        requires=[],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    pkg_b = ResolvedDependency(
        name=pkg_b_name,
        version="1.0.0",
        requires=[pkg_d_name],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    pkg_a = ResolvedDependency(
        name=pkg_a_name,
        version="1.0.0",
        requires=[pkg_b_name, pkg_c_name],
        platform_tags=["py3-none-any"],
        is_pure_python=True,
    )

    graph = DependencyGraph()
    graph.add_package(pkg_a)
    graph.add_package(pkg_b)
    graph.add_package(pkg_c)
    graph.add_package(pkg_d)
    graph.root_dependencies = [pkg_a_name]

    # Return graph and which packages should be excluded
    exclude_list = {pkg_c_name}  # Explicitly excluded
    core_ap_modules = frozenset({pkg_d_name})  # Core AP module

    return graph, pkg_a_name, pkg_b_name, pkg_c_name, pkg_d_name, exclude_list, core_ap_modules


class TestExclusionRulesConsistency:
    """Property-based tests for exclusion rules consistency.

    Feature: robust-vendoring, Property 2: Exclusion Rules Consistency
    Validates: Requirements 1.2, 1.3, 1.6
    """

    @given(data=dependency_graph_with_exclusions())
    @settings(max_examples=100)
    def test_excluded_packages_not_in_filtered_graph(self, data):
        """
        Property 2: Exclusion Rules Consistency - Exclude List

        *For any* package in the exclude list, that package SHALL NOT
        appear in the filtered DependencyGraph.

        **Validates: Requirements 1.2, 1.3, 1.6**
        """
        graph, _, _, pkg_c, _, exclude_list, _ = data

        # Filter the graph
        filtered = graph.filter_packages(exclude_list)

        # Excluded package should not be in filtered graph
        assert not filtered.has_package(pkg_c)
        assert pkg_c not in {pkg.name for pkg in filtered.get_all_packages()}

    @given(data=dependency_graph_with_exclusions())
    @settings(max_examples=100)
    def test_core_ap_modules_not_in_filtered_graph(self, data):
        """
        Property 2: Exclusion Rules Consistency - Core AP Modules

        *For any* Core AP module, that module SHALL NOT appear in the
        filtered DependencyGraph.

        **Validates: Requirements 1.2, 1.3, 1.6**
        """
        graph, _, _, _, pkg_d, _, core_ap_modules = data

        # Filter the graph using core AP modules as exclusions
        filtered = graph.filter_packages(core_ap_modules)

        # Core AP module should not be in filtered graph
        assert not filtered.has_package(pkg_d)

    @given(data=dependency_graph_with_exclusions())
    @settings(max_examples=100)
    def test_non_excluded_packages_remain_in_filtered_graph(self, data):
        """
        Property 2: Exclusion Rules Consistency - Non-excluded Packages

        *For any* package NOT in the exclude list or Core AP modules,
        that package SHALL remain in the filtered DependencyGraph.

        **Validates: Requirements 1.2, 1.3, 1.6**
        """
        graph, pkg_a, pkg_b, pkg_c, pkg_d, exclude_list, core_ap_modules = data

        # Combine all exclusions
        all_exclusions = exclude_list | core_ap_modules

        # Filter the graph
        filtered = graph.filter_packages(all_exclusions)

        # Non-excluded packages should remain
        assert filtered.has_package(pkg_a)
        assert filtered.has_package(pkg_b)

        # Excluded packages should be gone
        assert not filtered.has_package(pkg_c)
        assert not filtered.has_package(pkg_d)

    @given(data=dependency_graph_with_exclusions())
    @settings(max_examples=100)
    def test_requires_list_filtered_for_excluded_deps(self, data):
        """
        Property 2: Exclusion Rules Consistency - Requires Filtering

        *For any* package in the filtered graph, its requires list SHALL
        NOT contain any excluded packages.

        **Validates: Requirements 1.2, 1.3, 1.6**
        """
        graph, pkg_a, pkg_b, pkg_c, pkg_d, exclude_list, core_ap_modules = data

        all_exclusions = exclude_list | core_ap_modules
        filtered = graph.filter_packages(all_exclusions)

        # Check that no package's requires list contains excluded packages
        for pkg in filtered.get_all_packages():
            for req in pkg.requires:
                assert (
                    req not in all_exclusions
                ), f"Package {pkg.name} still requires excluded package {req}"

    @given(data=dependency_graph_with_exclusions())
    @settings(max_examples=100)
    def test_multiple_paths_to_excluded_package(self, data):
        """
        Property 2: Exclusion Rules Consistency - Multiple Paths

        *For any* excluded package reachable via multiple dependency paths,
        that package SHALL NOT appear in the filtered graph regardless of
        how many paths lead to it.

        **Validates: Requirements 1.2, 1.3, 1.6**
        """
        # Create a graph where excluded package is reachable via multiple paths
        graph, pkg_a, pkg_b, pkg_c, pkg_d, exclude_list, core_ap_modules = data

        # Add another path to pkg_c (the excluded package)
        # by making pkg_b also depend on pkg_c
        pkg_b_resolved = graph.get_package(pkg_b)
        if pkg_b_resolved:
            pkg_b_resolved.requires.append(pkg_c)

        # Filter should still exclude pkg_c
        filtered = graph.filter_packages(exclude_list)
        assert not filtered.has_package(pkg_c)

    @given(
        exclude_pkg=valid_package_names,
        other_pkg=valid_package_names,
    )
    @settings(max_examples=100)
    def test_should_include_respects_exclude_list(self, exclude_pkg, other_pkg):
        """
        Property 2: Exclusion Rules Consistency - should_include Method

        *For any* package in the exclude list, should_include() SHALL
        return False. For packages not in the exclude list, it SHALL
        return True (unless they are Core AP modules).

        **Validates: Requirements 1.2, 1.3, 1.6**
        """
        from island_vendor.resolver import DependencyResolver

        # Create resolver with exclude list
        resolver = DependencyResolver(
            exclude_packages={exclude_pkg},
            core_ap_modules=frozenset(),  # Empty to isolate exclude list test
        )

        # Excluded package should not be included
        assert not resolver.should_include(exclude_pkg)

        # Other package should be included (if not same as excluded)
        if other_pkg != exclude_pkg:
            assert resolver.should_include(other_pkg)
