# SPDX-License-Identifier: MIT
"""Dependency vendoring and import rewriting for APWorld packages.

This package provides utilities for vendoring Python dependencies into APWorld
packages and rewriting imports to use the vendored namespace.

Example:
    >>> from apworld_vendor import VendorConfig, vendor_dependencies, rewrite_imports
    >>>
    >>> # Create configuration from pyproject.toml
    >>> config = VendorConfig.from_pyproject("pyproject.toml")
    >>>
    >>> # Vendor dependencies
    >>> result = vendor_dependencies(config, target_dir="build/_vendor")
    >>>
    >>> # Rewrite imports in source files
    >>> rewrite_imports(
    ...     source_dir="src/my_game",
    ...     output_dir="build/my_game",
    ...     vendored_modules=result.get_vendored_module_names(),
    ...     config=config,
    ... )
"""

__version__ = "0.1.0"

from .config import (
    CORE_AP_MODULES,
    VendorConfig,
    VendorConfigError,
    VendoredPackage,
    VendorResult,
)
from .packager import (
    DependencyDownloadError,
    VendorPackageError,
    create_vendor_manifest,
    download_dependencies,
    vendor_dependencies,
)
from .rewriter import (
    ImportRewriteError,
    ImportRewriter,
    RewriteResult,
    rewrite_file,
    rewrite_imports,
    rewrite_source,
)

__all__ = [
    # Config
    "VendorConfig",
    "VendorConfigError",
    "VendoredPackage",
    "VendorResult",
    "CORE_AP_MODULES",
    # Packager
    "vendor_dependencies",
    "download_dependencies",
    "create_vendor_manifest",
    "DependencyDownloadError",
    "VendorPackageError",
    # Rewriter
    "rewrite_imports",
    "rewrite_file",
    "rewrite_source",
    "RewriteResult",
    "ImportRewriter",
    "ImportRewriteError",
]
