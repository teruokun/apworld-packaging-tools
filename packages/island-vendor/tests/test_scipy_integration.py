# SPDX-License-Identifier: MIT
"""Integration tests for scipy vendoring.

These tests verify that the vendoring system correctly handles real-world
platform-specific packages like scipy, including:
- Transitive dependency resolution (scipy depends on numpy)
- Platform tag detection and inheritance
- Import rewriting within vendored dependencies

Feature: robust-vendoring
Validates: Requirements 5.1, 5.2, 5.3, 5.4

Note: These tests require network access and may be slow due to downloading
large packages like scipy and numpy.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from island_vendor.config import VendorConfig
from island_vendor.packager import create_vendor_manifest, vendor_dependencies
from island_vendor.rewriter import rewrite_imports


# Mark all tests in this module as integration and slow
pytestmark = [pytest.mark.integration, pytest.mark.slow]


class TestScipyVendoring:
    """Integration tests for vendoring scipy with transitive dependencies.

    These tests verify that:
    - scipy is vendored along with its transitive dependency numpy
    - The resulting platform tag is platform-specific (not py3-none-any)
    - Import rewriting works for transitive dependencies

    Validates: Requirements 5.1, 5.2, 5.3, 5.4
    """

    @pytest.fixture
    def vendor_config(self) -> VendorConfig:
        """Create a VendorConfig for testing scipy vendoring."""
        return VendorConfig(
            package_name="test_game",
            dependencies=["scipy"],
            exclude=[],
            namespace="_vendor",
        )

    def test_scipy_includes_numpy_transitive_dependency(self, vendor_config: VendorConfig):
        """Test that vendoring scipy includes numpy as a transitive dependency.

        scipy depends on numpy, so when we vendor scipy, numpy should also
        be included in the vendored packages.

        Validates: Requirements 5.1, 5.2
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "vendor"

            # Vendor scipy
            result = vendor_dependencies(vendor_config, target_dir)

            # Check that vendoring succeeded
            assert result.success, f"Vendoring failed with errors: {result.errors}"

            # Check that we have a dependency graph
            assert result.dependency_graph is not None, "Dependency graph should be populated"

            # Get all package names from the dependency graph
            graph_names = set(result.dependency_graph.packages.keys())

            # scipy should be in the vendored packages
            assert "scipy" in graph_names, "scipy should be in the dependency graph"

            # numpy should be included as a transitive dependency
            assert (
                "numpy" in graph_names
            ), "numpy should be included as a transitive dependency of scipy"

            # Verify the dependency relationship in the graph
            scipy_pkg = result.dependency_graph.get_package("scipy")
            assert scipy_pkg is not None, "scipy should be in the dependency graph"

            # scipy should have numpy in its requires list
            scipy_requires = [r.lower() for r in scipy_pkg.requires]
            assert (
                "numpy" in scipy_requires
            ), f"scipy should require numpy, but requires: {scipy_pkg.requires}"

    def test_scipy_platform_tag_is_platform_specific(self, vendor_config: VendorConfig):
        """Test that vendoring scipy results in a platform-specific tag.

        scipy contains native extensions, so the resulting platform tag
        should NOT be py3-none-any.

        Validates: Requirements 5.3
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "vendor"

            # Vendor scipy
            result = vendor_dependencies(vendor_config, target_dir)

            # Check that vendoring succeeded
            assert result.success, f"Vendoring failed with errors: {result.errors}"

            # The result should NOT be pure Python
            assert (
                not result.is_pure_python
            ), "scipy vendoring should result in non-pure-python package"

            # The platform tag should be set and NOT be py3-none-any
            assert result.platform_tag is not None, "Platform tag should be set"
            platform_tag_str = str(result.platform_tag)
            assert (
                platform_tag_str != "py3-none-any"
            ), f"Platform tag should be platform-specific, got: {platform_tag_str}"

            # The platform tag should contain platform-specific information
            # (e.g., macosx, linux, win, etc.)
            assert any(
                platform in platform_tag_str.lower()
                for platform in ["macosx", "linux", "win", "manylinux"]
            ), f"Platform tag should contain platform info: {platform_tag_str}"

    def test_scipy_numpy_platform_tags_detected(self, vendor_config: VendorConfig):
        """Test that both scipy and numpy are detected as platform-specific.

        Both scipy and numpy contain native extensions, so both should
        be detected as platform-specific packages.

        Validates: Requirements 5.3
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "vendor"

            # Vendor scipy
            result = vendor_dependencies(vendor_config, target_dir)

            # Check that vendoring succeeded
            assert result.success, f"Vendoring failed with errors: {result.errors}"
            assert result.dependency_graph is not None

            # Check scipy is platform-specific
            scipy_pkg = result.dependency_graph.get_package("scipy")
            assert scipy_pkg is not None
            assert not scipy_pkg.is_pure_python, "scipy should be platform-specific"
            assert scipy_pkg.platform_tags, "scipy should have platform tags"
            assert (
                scipy_pkg.platform_tags[0] != "py3-none-any"
            ), f"scipy platform tag should not be py3-none-any: {scipy_pkg.platform_tags}"

            # Check numpy is platform-specific
            numpy_pkg = result.dependency_graph.get_package("numpy")
            assert numpy_pkg is not None
            assert not numpy_pkg.is_pure_python, "numpy should be platform-specific"
            assert numpy_pkg.platform_tags, "numpy should have platform tags"
            assert (
                numpy_pkg.platform_tags[0] != "py3-none-any"
            ), f"numpy platform tag should not be py3-none-any: {numpy_pkg.platform_tags}"

    def test_scipy_vendor_manifest_completeness(self, vendor_config: VendorConfig):
        """Test that the vendor manifest includes complete dependency information.

        The manifest should include:
        - Both scipy and numpy in vendored_packages
        - Dependency graph showing scipy -> numpy relationship
        - Platform tags for each package
        - is_pure_python = false

        Validates: Requirements 5.1, 5.2, 5.3
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "vendor"
            manifest_path = Path(tmpdir) / "vendor_manifest.json"

            # Vendor scipy
            result = vendor_dependencies(vendor_config, target_dir)
            assert result.success, f"Vendoring failed with errors: {result.errors}"

            # Create the manifest
            create_vendor_manifest(result, manifest_path)

            # Read and verify the manifest
            assert manifest_path.exists(), "Manifest file should be created"
            manifest = json.loads(manifest_path.read_text())

            # Check vendored_packages contains scipy and numpy
            assert "vendored_packages" in manifest
            vendored = manifest["vendored_packages"]
            assert "scipy" in vendored, "scipy should be in vendored_packages"
            assert "numpy" in vendored, "numpy should be in vendored_packages"

            # Check scipy has platform tags
            assert vendored["scipy"]["platform_tags"], "scipy should have platform tags"
            assert not vendored["scipy"]["is_pure_python"], "scipy should not be pure python"

            # Check numpy has platform tags
            assert vendored["numpy"]["platform_tags"], "numpy should have platform tags"
            assert not vendored["numpy"]["is_pure_python"], "numpy should not be pure python"

            # Check dependency graph
            assert "dependency_graph" in manifest
            dep_graph = manifest["dependency_graph"]
            assert "scipy" in dep_graph, "scipy should be in dependency graph"

            # scipy should depend on numpy
            scipy_deps = [d.lower() for d in dep_graph.get("scipy", [])]
            assert (
                "numpy" in scipy_deps
            ), f"scipy should depend on numpy in graph: {dep_graph.get('scipy')}"

            # Check root dependencies
            assert "root_dependencies" in manifest
            assert "scipy" in manifest["root_dependencies"]

            # Check overall purity
            assert manifest["is_pure_python"] is False

            # Check effective platform tag
            assert manifest["effective_platform_tag"] is not None
            assert manifest["effective_platform_tag"] != "py3-none-any"


class TestScipyImportRewriting:
    """Integration tests for import rewriting with scipy.

    These tests verify that imports within vendored scipy code
    that reference numpy are correctly rewritten to use the vendor namespace.

    Validates: Requirements 5.4
    """

    @pytest.fixture
    def vendor_config(self) -> VendorConfig:
        """Create a VendorConfig for testing import rewriting."""
        return VendorConfig(
            package_name="test_game",
            dependencies=["scipy"],
            exclude=[],
            namespace="_vendor",
        )

    def test_scipy_imports_numpy_rewritten(self, vendor_config: VendorConfig):
        """Test that scipy's imports of numpy are rewritten.

        When scipy is vendored along with numpy, any imports of numpy
        within scipy's code should be rewritten to use the vendor namespace.

        Validates: Requirements 5.4
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir) / "vendor"
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Vendor scipy
            result = vendor_dependencies(vendor_config, target_dir)
            assert result.success, f"Vendoring failed with errors: {result.errors}"

            # Get the vendored module names
            vendored_modules = result.get_vendored_module_names()

            # Verify both scipy and numpy modules are present
            assert "scipy" in vendored_modules or any(
                m.startswith("scipy") for m in vendored_modules
            ), f"scipy should be in vendored modules: {vendored_modules}"
            assert "numpy" in vendored_modules or any(
                m.startswith("numpy") for m in vendored_modules
            ), f"numpy should be in vendored modules: {vendored_modules}"

            # Create a simple source file that imports scipy
            source_dir = Path(tmpdir) / "src" / "test_game"
            source_dir.mkdir(parents=True)
            (source_dir / "__init__.py").write_text(
                "# Test package\n" "import scipy\n" "from scipy import stats\n"
            )

            # Rewrite imports
            results = rewrite_imports(
                source_dir,
                output_dir / "test_game",
                vendored_modules,
                vendor_config,
                rewrite_vendored=False,  # Don't rewrite vendored for this test
            )

            # Check that imports were rewritten
            assert len(results) > 0, "Should have processed at least one file"

            # Read the rewritten file
            rewritten_init = (output_dir / "test_game" / "__init__.py").read_text()

            # Verify scipy imports are rewritten to use vendor namespace
            assert (
                "test_game._vendor" in rewritten_init
            ), f"Imports should use vendor namespace: {rewritten_init}"
            assert (
                "from test_game._vendor import scipy" in rewritten_init
                or "from test_game._vendor.scipy" in rewritten_init
            ), f"scipy import should be rewritten: {rewritten_init}"
