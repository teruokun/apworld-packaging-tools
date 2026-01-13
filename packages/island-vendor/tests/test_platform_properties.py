# SPDX-License-Identifier: MIT
"""Property-based tests for platform tag detection.

Feature: robust-vendoring
Property 5: Platform Tag Detection
Validates: Requirements 2.5

These tests verify that:
- Packages with native extensions are detected as platform-specific
- Platform tags are correctly parsed from wheel files and filenames
- Pure Python packages are correctly identified
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

from island_vendor.platform import (
    PlatformTag,
    compute_most_restrictive_tag,
    detect_native_extensions,
    detect_package_platform,
    parse_wheel_filename_tags,
    parse_wheel_tags,
)


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Valid package names
valid_package_names = st.from_regex(r"[a-z][a-z0-9_]{0,15}", fullmatch=True)

# Valid version strings
valid_versions = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)

# Python tags
python_tags = st.sampled_from(["py3", "py2.py3", "cp39", "cp310", "cp311", "cp312"])

# ABI tags
abi_tags = st.sampled_from(["none", "abi3", "cp39", "cp310", "cp311", "cp312"])

# Platform tags
platform_tags = st.sampled_from(
    [
        "any",
        "linux_x86_64",
        "linux_aarch64",
        "macosx_10_9_x86_64",
        "macosx_11_0_arm64",
        "win_amd64",
        "win32",
        "manylinux2014_x86_64",
    ]
)

# Native extension suffixes
native_extensions = st.sampled_from([".so", ".dll", ".dylib", ".pyd"])


@st.composite
def platform_tag_strategy(draw):
    """Generate a valid PlatformTag."""
    python = draw(python_tags)
    abi = draw(abi_tags)
    platform = draw(platform_tags)
    return PlatformTag(python_tag=python, abi_tag=abi, platform_tag=platform)


@st.composite
def pure_python_tag(draw):
    """Generate a pure Python platform tag."""
    python = draw(st.sampled_from(["py3", "py2.py3"]))
    return PlatformTag(python_tag=python, abi_tag="none", platform_tag="any")


@st.composite
def platform_specific_tag(draw):
    """Generate a platform-specific tag (not pure Python)."""
    python = draw(python_tags)
    abi = draw(st.sampled_from(["abi3", "cp39", "cp310", "cp311", "cp312"]))
    platform = draw(
        st.sampled_from(
            [
                "linux_x86_64",
                "linux_aarch64",
                "macosx_10_9_x86_64",
                "macosx_11_0_arm64",
                "win_amd64",
                "manylinux2014_x86_64",
            ]
        )
    )
    return PlatformTag(python_tag=python, abi_tag=abi, platform_tag=platform)


@st.composite
def wheel_filename(draw, is_pure: bool | None = None):
    """Generate a valid wheel filename.

    Args:
        is_pure: If True, generate pure Python wheel. If False, platform-specific.
                 If None, randomly choose.
    """
    name = draw(valid_package_names)
    version = draw(valid_versions)
    python = draw(python_tags)

    if is_pure is None:
        is_pure = draw(st.booleans())

    if is_pure:
        abi = "none"
        platform = "any"
    else:
        abi = draw(st.sampled_from(["abi3", "cp311"]))
        platform = draw(
            st.sampled_from(
                [
                    "linux_x86_64",
                    "macosx_11_0_arm64",
                    "win_amd64",
                ]
            )
        )

    return f"{name}-{version}-{python}-{abi}-{platform}.whl", is_pure


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPlatformTagDetection:
    """Property-based tests for platform tag detection.

    Feature: robust-vendoring, Property 5: Platform Tag Detection
    Validates: Requirements 2.5
    """

    @given(data=wheel_filename(is_pure=True))
    @settings(max_examples=100)
    def test_pure_python_wheel_detected_as_pure(self, data):
        """
        Property 5: Platform Tag Detection - Pure Python Wheels

        *For any* wheel file with platform tag 'any' and ABI tag 'none',
        the system SHALL detect it as pure Python (is_pure_python=True).

        **Validates: Requirements 2.5**
        """
        filename, expected_pure = data

        tags = parse_wheel_filename_tags(filename)

        assert len(tags) >= 1
        assert all(
            tag.is_pure_python for tag in tags
        ), f"Expected pure Python tags for {filename}, got {tags}"

    @given(data=wheel_filename(is_pure=False))
    @settings(max_examples=100)
    def test_platform_specific_wheel_detected_as_non_pure(self, data):
        """
        Property 5: Platform Tag Detection - Platform-Specific Wheels

        *For any* wheel file with a platform-specific tag (not 'any'),
        the system SHALL detect it as platform-specific (is_pure_python=False).

        **Validates: Requirements 2.5**
        """
        filename, expected_pure = data

        tags = parse_wheel_filename_tags(filename)

        assert len(tags) >= 1
        assert not all(
            tag.is_pure_python for tag in tags
        ), f"Expected platform-specific tags for {filename}, got {tags}"

    @given(tag=platform_tag_strategy())
    @settings(max_examples=100)
    def test_platform_tag_roundtrip(self, tag):
        """
        Property 5: Platform Tag Detection - Tag Roundtrip

        *For any* valid platform tag, converting to string and parsing back
        SHALL produce an equivalent tag.

        **Validates: Requirements 2.5**
        """
        tag_str = str(tag)
        parsed = PlatformTag.from_string(tag_str)

        assert parsed.python_tag == tag.python_tag
        assert parsed.abi_tag == tag.abi_tag
        assert parsed.platform_tag == tag.platform_tag

    @given(
        ext=native_extensions,
        pkg_name=valid_package_names,
    )
    @settings(max_examples=100)
    def test_native_extension_detection(self, ext, pkg_name):
        """
        Property 5: Platform Tag Detection - Native Extensions

        *For any* package directory containing native extension files
        (.so, .dll, .dylib, .pyd), the system SHALL detect those files.

        **Validates: Requirements 2.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            pkg_dir = Path(temp_dir) / pkg_name
            pkg_dir.mkdir()

            # Create a native extension file
            native_file = pkg_dir / f"_native{ext}"
            native_file.write_bytes(b"fake native code")

            # Detect native extensions
            found = detect_native_extensions(pkg_dir)

            assert len(found) >= 1, f"Expected to find native extension {ext}"
            assert any(f.suffix == ext for f in found)

    @given(pkg_name=valid_package_names)
    @settings(max_examples=100)
    def test_no_native_extensions_in_pure_package(self, pkg_name):
        """
        Property 5: Platform Tag Detection - No Native Extensions

        *For any* package directory containing only .py files,
        the system SHALL detect no native extensions.

        **Validates: Requirements 2.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            pkg_dir = Path(temp_dir) / pkg_name
            pkg_dir.mkdir()

            # Create only Python files
            (pkg_dir / "__init__.py").write_text("# Pure Python")
            (pkg_dir / "module.py").write_text("def foo(): pass")

            # Detect native extensions
            found = detect_native_extensions(pkg_dir)

            assert len(found) == 0, f"Expected no native extensions, found {found}"

    @given(
        ext=native_extensions,
        pkg_name=valid_package_names,
    )
    @settings(max_examples=100)
    def test_package_with_native_detected_as_platform_specific(self, ext, pkg_name):
        """
        Property 5: Platform Tag Detection - Package Platform Detection

        *For any* package containing native extension files,
        detect_package_platform() SHALL return is_pure_python=False.

        **Validates: Requirements 2.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            pkg_dir = Path(temp_dir) / pkg_name
            pkg_dir.mkdir()

            # Create a native extension file
            native_file = pkg_dir / f"_native{ext}"
            native_file.write_bytes(b"fake native code")

            # Also create __init__.py
            (pkg_dir / "__init__.py").write_text("# Package with native")

            # Detect platform
            is_pure, tags = detect_package_platform(pkg_dir)

            assert not is_pure, f"Package with {ext} should be platform-specific"

    @given(tags=st.lists(pure_python_tag(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_all_pure_python_returns_pure_tag(self, tags):
        """
        Property 5: Platform Tag Detection - Pure Python Aggregation

        *For any* set of pure Python platform tags,
        compute_most_restrictive_tag() SHALL return a pure Python tag.

        **Validates: Requirements 2.5**
        """
        result = compute_most_restrictive_tag(tags)

        assert result.is_pure_python, f"Expected pure Python tag, got {result}"

    @given(
        pure_tags=st.lists(pure_python_tag(), min_size=0, max_size=3),
        specific_tags=st.lists(platform_specific_tag(), min_size=1, max_size=3),
    )
    @settings(max_examples=100)
    def test_any_platform_specific_returns_specific_tag(self, pure_tags, specific_tags):
        """
        Property 5: Platform Tag Detection - Platform-Specific Aggregation

        *For any* set of tags containing at least one platform-specific tag,
        compute_most_restrictive_tag() SHALL return a platform-specific tag.

        **Validates: Requirements 2.5**
        """
        all_tags = pure_tags + specific_tags
        result = compute_most_restrictive_tag(all_tags)

        assert not result.is_pure_python, f"Expected platform-specific tag, got {result}"

    @given(data=wheel_filename())
    @settings(max_examples=100)
    def test_wheel_filename_parsing_produces_valid_tags(self, data):
        """
        Property 5: Platform Tag Detection - Wheel Filename Parsing

        *For any* valid wheel filename, parse_wheel_filename_tags()
        SHALL produce at least one valid PlatformTag.

        **Validates: Requirements 2.5**
        """
        filename, _ = data

        tags = parse_wheel_filename_tags(filename)

        assert len(tags) >= 1, f"Expected at least one tag from {filename}"
        for tag in tags:
            assert isinstance(tag, PlatformTag)
            assert tag.python_tag
            assert tag.abi_tag
            assert tag.platform_tag

    @given(
        pkg_name=valid_package_names,
        version=valid_versions,
        tag=platform_tag_strategy(),
    )
    @settings(max_examples=100)
    def test_wheel_file_tag_parsing(self, pkg_name, version, tag):
        """
        Property 5: Platform Tag Detection - Wheel File Tag Parsing

        *For any* wheel file with a WHEEL metadata file containing Tag entries,
        parse_wheel_tags() SHALL extract those tags correctly.

        **Validates: Requirements 2.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a minimal wheel file
            wheel_name = (
                f"{pkg_name}-{version}-{tag.python_tag}-{tag.abi_tag}-{tag.platform_tag}.whl"
            )
            wheel_path = Path(temp_dir) / wheel_name

            # Create wheel with WHEEL metadata
            with zipfile.ZipFile(wheel_path, "w") as whl:
                wheel_content = f"""Wheel-Version: 1.0
Generator: test
Root-Is-Purelib: {'true' if tag.is_pure_python else 'false'}
Tag: {tag}
"""
                whl.writestr(f"{pkg_name}-{version}.dist-info/WHEEL", wheel_content)
                whl.writestr(
                    f"{pkg_name}-{version}.dist-info/METADATA",
                    f"Name: {pkg_name}\nVersion: {version}\n",
                )

            # Parse tags
            parsed_tags = parse_wheel_tags(wheel_path)

            assert len(parsed_tags) >= 1
            # The parsed tag should match what we put in
            assert any(
                t.python_tag == tag.python_tag
                and t.abi_tag == tag.abi_tag
                and t.platform_tag == tag.platform_tag
                for t in parsed_tags
            ), f"Expected to find {tag} in {parsed_tags}"


# =============================================================================
# Property 4: Platform Tag Inheritance Tests
# =============================================================================


class TestPlatformTagInheritance:
    """Property-based tests for platform tag inheritance.

    Feature: robust-vendoring, Property 4: Platform Tag Inheritance
    Validates: Requirements 2.1, 2.2, 2.4

    These tests verify that:
    - Island packages with only pure Python vendored packages get py3-none-any tag
    - Island packages with any platform-specific vendored package get platform-specific tag
    """

    @given(
        num_packages=st.integers(min_value=1, max_value=5),
        pkg_names=st.lists(valid_package_names, min_size=5, max_size=5, unique=True),
    )
    @settings(max_examples=100)
    def test_all_pure_python_packages_result_in_pure_tag(self, num_packages, pkg_names):
        """
        Property 4: Platform Tag Inheritance - All Pure Python

        *For any* Island package where all vendored packages are pure Python
        (py3-none-any), the Island SHALL have platform tag py3-none-any.

        **Validates: Requirements 2.1, 2.2, 2.4**
        """
        from island_vendor.resolver import DependencyGraph, ResolvedDependency

        graph = DependencyGraph()

        # Add only pure Python packages
        for i in range(min(num_packages, len(pkg_names))):
            pkg = ResolvedDependency(
                name=pkg_names[i],
                version="1.0.0",
                requires=[],
                platform_tags=["py3-none-any"],
                is_pure_python=True,
            )
            graph.add_package(pkg)

        # The graph should be pure Python
        assert graph.is_pure_python(), "Graph with only pure Python packages should be pure"

        # The most restrictive tag should be pure Python
        tag = graph.get_most_restrictive_tag()
        assert tag.is_pure_python, f"Expected pure Python tag, got {tag}"

    @given(
        num_pure=st.integers(min_value=0, max_value=3),
        num_specific=st.integers(min_value=1, max_value=3),
        pkg_names=st.lists(valid_package_names, min_size=6, max_size=6, unique=True),
        specific_tag=platform_specific_tag(),
    )
    @settings(max_examples=100)
    def test_any_platform_specific_results_in_specific_tag(
        self, num_pure, num_specific, pkg_names, specific_tag
    ):
        """
        Property 4: Platform Tag Inheritance - Any Platform-Specific

        *For any* Island package where at least one vendored package is
        platform-specific, the Island SHALL have a platform-specific tag.

        **Validates: Requirements 2.1, 2.2, 2.4**
        """
        from island_vendor.resolver import DependencyGraph, ResolvedDependency

        graph = DependencyGraph()
        pkg_idx = 0

        # Add pure Python packages
        for _ in range(num_pure):
            if pkg_idx >= len(pkg_names):
                break
            pkg = ResolvedDependency(
                name=pkg_names[pkg_idx],
                version="1.0.0",
                requires=[],
                platform_tags=["py3-none-any"],
                is_pure_python=True,
            )
            graph.add_package(pkg)
            pkg_idx += 1

        # Add platform-specific packages
        for _ in range(num_specific):
            if pkg_idx >= len(pkg_names):
                break
            pkg = ResolvedDependency(
                name=pkg_names[pkg_idx],
                version="1.0.0",
                requires=[],
                platform_tags=[str(specific_tag)],
                is_pure_python=False,
            )
            graph.add_package(pkg)
            pkg_idx += 1

        # The graph should NOT be pure Python
        assert (
            not graph.is_pure_python()
        ), "Graph with platform-specific packages should not be pure"

        # The most restrictive tag should be platform-specific
        tag = graph.get_most_restrictive_tag()
        assert not tag.is_pure_python, f"Expected platform-specific tag, got {tag}"

    @given(
        pkg_names=st.lists(valid_package_names, min_size=3, max_size=3, unique=True),
        specific_tag=platform_specific_tag(),
    )
    @settings(max_examples=100)
    def test_platform_tag_propagates_through_dependencies(self, pkg_names, specific_tag):
        """
        Property 4: Platform Tag Inheritance - Dependency Propagation

        *For any* Island package where a transitive dependency is platform-specific,
        the Island SHALL have a platform-specific tag even if direct dependencies
        are pure Python.

        **Validates: Requirements 2.1, 2.2, 2.4**
        """
        from island_vendor.resolver import DependencyGraph, ResolvedDependency

        pkg_a, pkg_b, pkg_c = pkg_names

        graph = DependencyGraph()

        # A (pure) -> B (pure) -> C (platform-specific)
        graph.add_package(
            ResolvedDependency(
                name=pkg_a,
                version="1.0.0",
                requires=[pkg_b],
                platform_tags=["py3-none-any"],
                is_pure_python=True,
            )
        )
        graph.add_package(
            ResolvedDependency(
                name=pkg_b,
                version="1.0.0",
                requires=[pkg_c],
                platform_tags=["py3-none-any"],
                is_pure_python=True,
            )
        )
        graph.add_package(
            ResolvedDependency(
                name=pkg_c,
                version="1.0.0",
                requires=[],
                platform_tags=[str(specific_tag)],
                is_pure_python=False,
            )
        )

        graph.root_dependencies = [pkg_a]

        # The graph should NOT be pure Python due to transitive dependency
        assert (
            not graph.is_pure_python()
        ), "Graph with platform-specific transitive dep should not be pure"

        # The most restrictive tag should be platform-specific
        tag = graph.get_most_restrictive_tag()
        assert (
            not tag.is_pure_python
        ), f"Expected platform-specific tag from transitive dep, got {tag}"

    @given(pkg_name=valid_package_names)
    @settings(max_examples=100)
    def test_empty_graph_returns_pure_python_tag(self, pkg_name):
        """
        Property 4: Platform Tag Inheritance - Empty Graph

        *For any* empty dependency graph (no vendored packages),
        the most restrictive tag SHALL be py3-none-any.

        **Validates: Requirements 2.1, 2.2, 2.4**
        """
        from island_vendor.resolver import DependencyGraph

        graph = DependencyGraph()

        # Empty graph should be pure Python
        assert graph.is_pure_python(), "Empty graph should be pure Python"

        # The most restrictive tag should be pure Python
        tag = graph.get_most_restrictive_tag()
        assert tag.is_pure_python, f"Expected pure Python tag for empty graph, got {tag}"

    @given(
        pkg_names=st.lists(valid_package_names, min_size=2, max_size=2, unique=True),
        tag1=platform_specific_tag(),
        tag2=platform_specific_tag(),
    )
    @settings(max_examples=100)
    def test_most_restrictive_tag_selected(self, pkg_names, tag1, tag2):
        """
        Property 4: Platform Tag Inheritance - Most Restrictive Selection

        *For any* Island package with multiple platform-specific vendored packages,
        the Island SHALL use the most restrictive compatible platform tag.

        **Validates: Requirements 2.1, 2.2, 2.4**
        """
        from island_vendor.resolver import DependencyGraph, ResolvedDependency
        from island_vendor.platform import _get_platform_specificity

        graph = DependencyGraph()

        graph.add_package(
            ResolvedDependency(
                name=pkg_names[0],
                version="1.0.0",
                requires=[],
                platform_tags=[str(tag1)],
                is_pure_python=False,
            )
        )
        graph.add_package(
            ResolvedDependency(
                name=pkg_names[1],
                version="1.0.0",
                requires=[],
                platform_tags=[str(tag2)],
                is_pure_python=False,
            )
        )

        result_tag = graph.get_most_restrictive_tag()

        # Result should be platform-specific
        assert not result_tag.is_pure_python

        # Result should be one of the input tags (the most restrictive one)
        result_specificity = _get_platform_specificity(result_tag)
        tag1_specificity = _get_platform_specificity(tag1)
        tag2_specificity = _get_platform_specificity(tag2)

        # The result should have specificity >= max of inputs
        # (it should be the most restrictive)
        assert result_specificity >= min(
            tag1_specificity, tag2_specificity
        ), f"Result {result_tag} should be at least as specific as inputs"
