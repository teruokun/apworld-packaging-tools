# SPDX-License-Identifier: MIT
"""Property-based tests for vendored import rewriting.

Feature: robust-vendoring
Property 3: Vendored Import Rewriting
Validates: Requirements 1.7

These tests verify that:
- Imports within vendored dependencies are rewritten to use the vendor namespace
- When scipy imports numpy, and both are vendored, the import is rewritten
- The rewrite_vendored parameter controls whether vendor directory is processed
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from island_vendor.config import CORE_AP_MODULES, VendorConfig
from island_vendor.rewriter import (
    rewrite_imports,
    rewrite_source,
    rewrite_vendored_imports,
)


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Python keywords that cannot be used as module names
PYTHON_KEYWORDS = frozenset(
    {
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    }
)

# Valid Python module names (excluding keywords)
valid_module_names = st.from_regex(r"[a-z][a-z0-9_]{0,15}", fullmatch=True).filter(
    lambda x: x not in PYTHON_KEYWORDS and x not in CORE_AP_MODULES
)

# Valid package names (can include hyphens, excluding keywords)
valid_package_names = st.from_regex(r"[a-z][a-z0-9_]{0,15}", fullmatch=True).filter(
    lambda x: x not in PYTHON_KEYWORDS and x not in CORE_AP_MODULES
)


@st.composite
def valid_vendor_configs(draw):
    """Generate valid VendorConfig instances."""
    package_name = draw(valid_package_names)
    namespace = draw(st.sampled_from(["_vendor", "_deps", "_lib"]))
    return VendorConfig(
        package_name=package_name,
        dependencies=[],
        exclude=[],
        namespace=namespace,
    )


@st.composite
def vendored_module_pair(draw):
    """Generate a pair of vendored module names (e.g., scipy and numpy)."""
    # Generate two unique module names
    module1 = draw(valid_module_names)
    module2 = draw(valid_module_names.filter(lambda x: x != module1))
    return module1, module2


@st.composite
def import_statement_types(draw, importing_module: str):
    """Generate different types of import statements for a module."""
    import_type = draw(st.sampled_from(["simple", "from", "from_dotted", "alias", "from_alias"]))

    if import_type == "simple":
        return f"import {importing_module}"
    elif import_type == "from":
        attr = draw(valid_module_names)
        return f"from {importing_module} import {attr}"
    elif import_type == "from_dotted":
        submodule = draw(valid_module_names)
        attr = draw(valid_module_names)
        return f"from {importing_module}.{submodule} import {attr}"
    elif import_type == "alias":
        alias = draw(valid_module_names)
        return f"import {importing_module} as {alias}"
    else:  # from_alias
        attr = draw(valid_module_names)
        alias = draw(valid_module_names)
        return f"from {importing_module} import {attr} as {alias}"


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestVendoredImportRewriting:
    """Property-based tests for vendored import rewriting.

    Feature: robust-vendoring, Property 3: Vendored Import Rewriting
    Validates: Requirements 1.7
    """

    @given(
        config=valid_vendor_configs(),
        module_pair=vendored_module_pair(),
    )
    @settings(max_examples=100)
    def test_vendored_import_simple_rewritten(
        self, config: VendorConfig, module_pair: tuple[str, str]
    ):
        """
        Property 3: Vendored Import Rewriting - Simple Import

        *For any* vendored package that contains `import other_vendored`,
        that import SHALL be rewritten to `from {namespace} import other_vendored`.

        **Validates: Requirements 1.7**
        """
        importing_pkg, imported_pkg = module_pair
        vendored_modules = {importing_pkg, imported_pkg}

        # Source code in the importing package that imports the other vendored package
        source = f"import {imported_pkg}"

        result, rewritten, preserved = rewrite_source(
            source,
            vendored_modules,
            config.vendor_namespace,
            config.core_ap_modules,
        )

        # The import should be rewritten to use the vendor namespace
        expected = f"from {config.vendor_namespace} import {imported_pkg}"
        assert expected in result, f"Expected '{expected}' in result, got: {result}"
        assert rewritten == 1
        assert preserved == 0

    @given(
        config=valid_vendor_configs(),
        module_pair=vendored_module_pair(),
    )
    @settings(max_examples=100)
    def test_vendored_import_from_rewritten(
        self, config: VendorConfig, module_pair: tuple[str, str]
    ):
        """
        Property 3: Vendored Import Rewriting - From Import

        *For any* vendored package that contains `from other_vendored import X`,
        that import SHALL be rewritten to `from {namespace}.other_vendored import X`.

        **Validates: Requirements 1.7**
        """
        importing_pkg, imported_pkg = module_pair
        vendored_modules = {importing_pkg, imported_pkg}

        source = f"from {imported_pkg} import something"

        result, rewritten, preserved = rewrite_source(
            source,
            vendored_modules,
            config.vendor_namespace,
            config.core_ap_modules,
        )

        expected = f"from {config.vendor_namespace}.{imported_pkg} import something"
        assert expected in result, f"Expected '{expected}' in result, got: {result}"
        assert rewritten == 1

    @given(
        config=valid_vendor_configs(),
        module_pair=vendored_module_pair(),
    )
    @settings(max_examples=100)
    def test_vendored_import_dotted_rewritten(
        self, config: VendorConfig, module_pair: tuple[str, str]
    ):
        """
        Property 3: Vendored Import Rewriting - Dotted Import

        *For any* vendored package that contains `from other_vendored.sub import X`,
        that import SHALL be rewritten to `from {namespace}.other_vendored.sub import X`.

        **Validates: Requirements 1.7**
        """
        importing_pkg, imported_pkg = module_pair
        vendored_modules = {importing_pkg, imported_pkg}

        source = f"from {imported_pkg}.submodule import func"

        result, rewritten, preserved = rewrite_source(
            source,
            vendored_modules,
            config.vendor_namespace,
            config.core_ap_modules,
        )

        expected = f"from {config.vendor_namespace}.{imported_pkg}.submodule import func"
        assert expected in result, f"Expected '{expected}' in result, got: {result}"
        assert rewritten == 1

    @given(
        config=valid_vendor_configs(),
        module_pair=vendored_module_pair(),
    )
    @settings(max_examples=100)
    def test_vendored_import_with_alias_rewritten(
        self, config: VendorConfig, module_pair: tuple[str, str]
    ):
        """
        Property 3: Vendored Import Rewriting - Import with Alias

        *For any* vendored package that contains `import other_vendored as alias`,
        that import SHALL be rewritten preserving the alias.

        **Validates: Requirements 1.7**
        """
        importing_pkg, imported_pkg = module_pair
        vendored_modules = {importing_pkg, imported_pkg}

        source = f"import {imported_pkg} as np"

        result, rewritten, preserved = rewrite_source(
            source,
            vendored_modules,
            config.vendor_namespace,
            config.core_ap_modules,
        )

        expected = f"from {config.vendor_namespace} import {imported_pkg} as np"
        assert expected in result, f"Expected '{expected}' in result, got: {result}"
        assert rewritten == 1

    @given(
        config=valid_vendor_configs(),
        module_pair=vendored_module_pair(),
    )
    @settings(max_examples=100)
    def test_rewrite_vendored_imports_processes_vendor_dir(
        self, config: VendorConfig, module_pair: tuple[str, str]
    ):
        """
        Property 3: Vendored Import Rewriting - Vendor Directory Processing

        *For any* vendor directory containing Python files with imports of
        other vendored packages, rewrite_vendored_imports() SHALL rewrite
        those imports in place.

        **Validates: Requirements 1.7**
        """
        importing_pkg, imported_pkg = module_pair
        vendored_modules = {importing_pkg, imported_pkg}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create the vendor directory structure
            normalized_name = config.package_name.replace("-", "_")
            vendor_dir = output_dir / normalized_name / config.namespace
            pkg_dir = vendor_dir / importing_pkg
            pkg_dir.mkdir(parents=True)

            # Create a Python file in the vendored package that imports another vendored package
            source_file = pkg_dir / "__init__.py"
            original_source = f"import {imported_pkg}\nfrom {imported_pkg} import something"
            source_file.write_text(original_source, encoding="utf-8")

            # Rewrite imports in the vendor directory
            results = rewrite_vendored_imports(output_dir, vendored_modules, config)

            # Check that the file was processed
            assert len(results) == 1
            assert results[0].imports_rewritten == 2

            # Verify the file was rewritten
            rewritten_content = source_file.read_text(encoding="utf-8")
            assert config.vendor_namespace in rewritten_content
            assert f"from {config.vendor_namespace} import {imported_pkg}" in rewritten_content
            assert (
                f"from {config.vendor_namespace}.{imported_pkg} import something"
                in rewritten_content
            )

    @given(
        config=valid_vendor_configs(),
        module_pair=vendored_module_pair(),
    )
    @settings(max_examples=100)
    def test_rewrite_imports_with_rewrite_vendored_true(
        self, config: VendorConfig, module_pair: tuple[str, str]
    ):
        """
        Property 3: Vendored Import Rewriting - rewrite_vendored=True

        *For any* call to rewrite_imports() with rewrite_vendored=True,
        imports within the vendor directory SHALL also be rewritten.

        **Validates: Requirements 1.7**
        """
        importing_pkg, imported_pkg = module_pair
        vendored_modules = {importing_pkg, imported_pkg}

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "src"
            output_dir = Path(tmpdir) / "output"

            # Create source directory with a simple file
            normalized_name = config.package_name.replace("-", "_")
            src_pkg_dir = source_dir / normalized_name
            src_pkg_dir.mkdir(parents=True)
            (src_pkg_dir / "__init__.py").write_text(f"import {imported_pkg}", encoding="utf-8")

            # Create vendor directory in output with vendored package
            vendor_dir = output_dir / normalized_name / config.namespace
            vendored_pkg_dir = vendor_dir / importing_pkg
            vendored_pkg_dir.mkdir(parents=True)
            vendor_init = vendored_pkg_dir / "__init__.py"
            vendor_init.write_text(f"import {imported_pkg}", encoding="utf-8")

            # Rewrite imports with rewrite_vendored=True (default)
            results = rewrite_imports(
                source_dir, output_dir, vendored_modules, config, rewrite_vendored=True
            )

            # Should have processed both source file and vendor file
            assert len(results) >= 2

            # Verify vendor file was rewritten
            rewritten_vendor = vendor_init.read_text(encoding="utf-8")
            assert config.vendor_namespace in rewritten_vendor

    @given(
        config=valid_vendor_configs(),
        module_pair=vendored_module_pair(),
    )
    @settings(max_examples=100)
    def test_rewrite_imports_with_rewrite_vendored_false(
        self, config: VendorConfig, module_pair: tuple[str, str]
    ):
        """
        Property 3: Vendored Import Rewriting - rewrite_vendored=False

        *For any* call to rewrite_imports() with rewrite_vendored=False,
        imports within the vendor directory SHALL NOT be rewritten.

        **Validates: Requirements 1.7**
        """
        importing_pkg, imported_pkg = module_pair
        vendored_modules = {importing_pkg, imported_pkg}

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "src"
            output_dir = Path(tmpdir) / "output"

            # Create source directory
            normalized_name = config.package_name.replace("-", "_")
            src_pkg_dir = source_dir / normalized_name
            src_pkg_dir.mkdir(parents=True)
            (src_pkg_dir / "__init__.py").write_text(f"import {imported_pkg}", encoding="utf-8")

            # Create vendor directory in output with vendored package
            vendor_dir = output_dir / normalized_name / config.namespace
            vendored_pkg_dir = vendor_dir / importing_pkg
            vendored_pkg_dir.mkdir(parents=True)
            vendor_init = vendored_pkg_dir / "__init__.py"
            original_vendor_content = f"import {imported_pkg}"
            vendor_init.write_text(original_vendor_content, encoding="utf-8")

            # Rewrite imports with rewrite_vendored=False
            results = rewrite_imports(
                source_dir, output_dir, vendored_modules, config, rewrite_vendored=False
            )

            # Should only have processed source file, not vendor file
            assert len(results) == 1

            # Verify vendor file was NOT rewritten
            vendor_content = vendor_init.read_text(encoding="utf-8")
            assert vendor_content == original_vendor_content
            assert config.vendor_namespace not in vendor_content

    @given(
        config=valid_vendor_configs(),
        module_pair=vendored_module_pair(),
    )
    @settings(max_examples=100)
    def test_vendored_relative_imports_preserved(
        self, config: VendorConfig, module_pair: tuple[str, str]
    ):
        """
        Property 3: Vendored Import Rewriting - Relative Imports Preserved

        *For any* vendored package with relative imports, those relative
        imports SHALL be preserved unchanged.

        **Validates: Requirements 1.7**
        """
        importing_pkg, imported_pkg = module_pair
        vendored_modules = {importing_pkg, imported_pkg}

        # Source with both relative and absolute imports
        source = f"""from . import utils
from .. import common
import {imported_pkg}
"""

        result, rewritten, preserved = rewrite_source(
            source,
            vendored_modules,
            config.vendor_namespace,
            config.core_ap_modules,
        )

        # Relative imports should be preserved
        assert "from . import utils" in result
        assert "from .. import common" in result

        # Absolute vendored import should be rewritten
        assert config.vendor_namespace in result
        assert rewritten == 1
        assert preserved == 2

    @given(
        config=valid_vendor_configs(),
        module_pair=vendored_module_pair(),
    )
    @settings(max_examples=100)
    def test_vendored_stdlib_imports_preserved(
        self, config: VendorConfig, module_pair: tuple[str, str]
    ):
        """
        Property 3: Vendored Import Rewriting - Stdlib Imports Preserved

        *For any* vendored package with standard library imports, those
        imports SHALL be preserved unchanged (not rewritten).

        **Validates: Requirements 1.7**
        """
        importing_pkg, imported_pkg = module_pair
        vendored_modules = {importing_pkg, imported_pkg}

        source = f"""import os
import sys
from pathlib import Path
import {imported_pkg}
"""

        result, rewritten, preserved = rewrite_source(
            source,
            vendored_modules,
            config.vendor_namespace,
            config.core_ap_modules,
        )

        # Stdlib imports should be preserved
        assert "import os" in result
        assert "import sys" in result
        assert "from pathlib import Path" in result

        # Only the vendored import should be rewritten
        assert rewritten == 1
        assert preserved == 3
