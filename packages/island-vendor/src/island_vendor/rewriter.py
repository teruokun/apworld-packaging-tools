# SPDX-License-Identifier: MIT
"""AST-based import rewriting for vendored dependencies.

This module transforms Python source files to rewrite imports of vendored
packages to use the package-specific vendor namespace, while preserving
imports from Core Archipelago modules unchanged.

Example:
    Original:
        import yaml
        from pydantic import BaseModel

    Rewritten (for package "my_game"):
        from my_game._vendor import yaml
        from my_game._vendor.pydantic import BaseModel
"""

from __future__ import annotations

import ast
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import VendorConfig


class ImportRewriteError(Exception):
    """Raised when import rewriting fails."""

    pass


@dataclass
class RewriteResult:
    """Result of rewriting imports in a file.

    Attributes:
        source_path: Original source file path
        output_path: Output file path
        imports_rewritten: Number of imports that were rewritten
        imports_preserved: Number of imports that were preserved (Core AP)
        modified: Whether the file was modified
    """

    source_path: Path
    output_path: Path
    imports_rewritten: int = 0
    imports_preserved: int = 0
    modified: bool = False


class ImportRewriter(ast.NodeTransformer):
    """AST transformer that rewrites imports to use vendored namespace.

    This transformer handles:
    - `import foo` -> `from {package}._vendor import foo`
    - `import foo.bar` -> `from {package}._vendor.foo import bar`
    - `from foo import bar` -> `from {package}._vendor.foo import bar`
    - `from foo.bar import baz` -> `from {package}._vendor.foo.bar import baz`

    Core AP imports are preserved unchanged.
    """

    def __init__(
        self,
        vendored_modules: set[str],
        vendor_namespace: str,
        core_ap_modules: frozenset[str],
    ) -> None:
        """Initialize the import rewriter.

        Args:
            vendored_modules: Set of top-level module names that are vendored
            vendor_namespace: Full vendor namespace (e.g., "my_game._vendor")
            core_ap_modules: Set of Core AP module names to preserve
        """
        super().__init__()
        self.vendored_modules = vendored_modules
        self.vendor_namespace = vendor_namespace
        self.core_ap_modules = core_ap_modules
        self.imports_rewritten = 0
        self.imports_preserved = 0

    def _is_vendored_module(self, module_name: str) -> bool:
        """Check if a module should be rewritten to use vendor namespace."""
        if not module_name:
            return False
        top_level = module_name.split(".")[0]
        # Don't rewrite Core AP modules
        if top_level in self.core_ap_modules:
            return False
        # Only rewrite if it's in our vendored modules
        return top_level in self.vendored_modules

    def visit_Import(self, node: ast.Import) -> ast.AST:
        """Transform `import foo` statements.

        Transforms:
            import yaml -> from my_game._vendor import yaml
            import yaml.parser -> from my_game._vendor.yaml import parser
        """
        new_nodes: list[ast.AST] = []

        for alias in node.names:
            module_name = alias.name
            asname = alias.asname

            if self._is_vendored_module(module_name):
                self.imports_rewritten += 1

                # Split module path
                parts = module_name.split(".")

                if len(parts) == 1:
                    # Simple import: import yaml
                    # -> from my_game._vendor import yaml
                    new_node = ast.ImportFrom(
                        module=self.vendor_namespace,
                        names=[ast.alias(name=parts[0], asname=asname)],
                        level=0,
                    )
                else:
                    # Dotted import: import yaml.parser
                    # -> from my_game._vendor.yaml import parser
                    vendor_module = f"{self.vendor_namespace}.{'.'.join(parts[:-1])}"
                    import_name = parts[-1]
                    # If no asname, use the full original name for binding
                    effective_asname = asname if asname else module_name
                    new_node = ast.ImportFrom(
                        module=vendor_module,
                        names=[ast.alias(name=import_name, asname=effective_asname)],
                        level=0,
                    )

                ast.copy_location(new_node, node)
                new_nodes.append(new_node)
            else:
                self.imports_preserved += 1
                # Keep original import for this alias
                preserved = ast.Import(names=[alias])
                ast.copy_location(preserved, node)
                new_nodes.append(preserved)

        if len(new_nodes) == 1:
            return new_nodes[0]
        else:
            # Return multiple nodes - caller needs to handle this
            return new_nodes  # type: ignore[return-value]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST:
        """Transform `from foo import bar` statements.

        Transforms:
            from yaml import safe_load -> from my_game._vendor.yaml import safe_load
            from yaml.parser import Parser -> from my_game._vendor.yaml.parser import Parser

        Preserves:
            from BaseClasses import Item -> unchanged
            from worlds.generic import Rules -> unchanged
        """
        module_name = node.module or ""

        # Handle relative imports - preserve them unchanged
        if node.level > 0:
            self.imports_preserved += 1
            return node

        if self._is_vendored_module(module_name):
            self.imports_rewritten += 1

            # Rewrite to use vendor namespace
            new_module = f"{self.vendor_namespace}.{module_name}"
            new_node = ast.ImportFrom(
                module=new_module,
                names=node.names,
                level=0,
            )
            ast.copy_location(new_node, node)
            return new_node
        else:
            self.imports_preserved += 1
            return node


def rewrite_source(
    source: str,
    vendored_modules: set[str],
    vendor_namespace: str,
    core_ap_modules: frozenset[str],
    filename: str = "<string>",
) -> tuple[str, int, int]:
    """Rewrite imports in Python source code.

    Args:
        source: Python source code
        vendored_modules: Set of top-level module names that are vendored
        vendor_namespace: Full vendor namespace (e.g., "my_game._vendor")
        core_ap_modules: Set of Core AP module names to preserve
        filename: Filename for error messages

    Returns:
        Tuple of (rewritten_source, imports_rewritten, imports_preserved)

    Raises:
        ImportRewriteError: If the source cannot be parsed
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        raise ImportRewriteError(f"Syntax error in {filename}: {e}") from e

    rewriter = ImportRewriter(vendored_modules, vendor_namespace, core_ap_modules)

    # Transform the AST
    new_body: list[ast.stmt] = []
    for node in tree.body:
        result = rewriter.visit(node)
        if isinstance(result, list):
            new_body.extend(result)  # type: ignore[arg-type]
        else:
            new_body.append(result)  # type: ignore[arg-type]

    tree.body = new_body
    ast.fix_missing_locations(tree)

    # Convert back to source
    try:
        rewritten = ast.unparse(tree)
    except Exception as e:
        raise ImportRewriteError(f"Failed to unparse AST for {filename}: {e}") from e

    return rewritten, rewriter.imports_rewritten, rewriter.imports_preserved


def rewrite_file(
    source_path: Path,
    output_path: Path,
    vendored_modules: set[str],
    vendor_namespace: str,
    core_ap_modules: frozenset[str],
) -> RewriteResult:
    """Rewrite imports in a single Python file.

    Args:
        source_path: Path to the source file
        output_path: Path to write the rewritten file
        vendored_modules: Set of top-level module names that are vendored
        vendor_namespace: Full vendor namespace
        core_ap_modules: Set of Core AP module names to preserve

    Returns:
        RewriteResult with statistics

    Raises:
        ImportRewriteError: If rewriting fails
    """
    result = RewriteResult(source_path=source_path, output_path=output_path)

    try:
        source = source_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ImportRewriteError(f"Failed to read {source_path}: {e}") from e

    rewritten, imports_rewritten, imports_preserved = rewrite_source(
        source,
        vendored_modules,
        vendor_namespace,
        core_ap_modules,
        filename=str(source_path),
    )

    result.imports_rewritten = imports_rewritten
    result.imports_preserved = imports_preserved
    result.modified = rewritten != source

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the rewritten source
    try:
        output_path.write_text(rewritten, encoding="utf-8")
    except Exception as e:
        raise ImportRewriteError(f"Failed to write {output_path}: {e}") from e

    return result


def rewrite_imports(
    source_dir: str | Path,
    output_dir: str | Path,
    vendored_modules: set[str],
    config: "VendorConfig",
    *,
    rewrite_vendored: bool = True,
) -> list[RewriteResult]:
    """Rewrite imports in all Python files in a directory.

    This function recursively processes all .py files in source_dir,
    rewriting imports of vendored packages to use the vendor namespace.

    When rewrite_vendored=True, also rewrites imports within the vendored
    dependencies themselves (in the vendor directory).

    Args:
        source_dir: Directory containing source files
        output_dir: Directory to write rewritten files
        vendored_modules: Set of top-level module names that are vendored
        config: Vendor configuration
        rewrite_vendored: If True, also rewrite imports within the vendor
            directory (default: True)

    Returns:
        List of RewriteResult for each processed file

    Raises:
        ImportRewriteError: If rewriting fails for any file
    """
    source_path = Path(source_dir)
    output_path = Path(output_dir)

    if not source_path.exists():
        raise ImportRewriteError(f"Source directory does not exist: {source_path}")

    results: list[RewriteResult] = []

    # Process all Python files
    for py_file in source_path.rglob("*.py"):
        # Calculate relative path and output location
        rel_path = py_file.relative_to(source_path)
        out_file = output_path / rel_path

        result = rewrite_file(
            py_file,
            out_file,
            vendored_modules,
            config.vendor_namespace,
            config.core_ap_modules,
        )
        results.append(result)

    # Copy non-Python files unchanged
    for other_file in source_path.rglob("*"):
        if other_file.is_file() and other_file.suffix != ".py":
            rel_path = other_file.relative_to(source_path)
            out_file = output_path / rel_path
            out_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(other_file, out_file)

    # Rewrite imports within the vendor directory if requested
    if rewrite_vendored:
        vendor_results = rewrite_vendored_imports(
            output_path,
            vendored_modules,
            config,
        )
        results.extend(vendor_results)

    return results


def rewrite_vendored_imports(
    output_dir: str | Path,
    vendored_modules: set[str],
    config: "VendorConfig",
) -> list[RewriteResult]:
    """Rewrite imports within vendored dependencies.

    This function processes Python files in the vendor directory,
    rewriting imports between vendored packages to use the vendor namespace.

    For example, if scipy imports numpy, and both are vendored, the import
    `import numpy` in scipy's code becomes `from my_game._vendor import numpy`.

    Args:
        output_dir: Directory containing the output (with vendor subdirectory)
        vendored_modules: Set of top-level module names that are vendored
        config: Vendor configuration

    Returns:
        List of RewriteResult for each processed file in the vendor directory

    Raises:
        ImportRewriteError: If rewriting fails for any file
    """
    output_path = Path(output_dir)

    # Normalize package name to get the vendor directory path
    normalized_name = config.package_name.replace("-", "_")
    vendor_dir = output_path / normalized_name / config.namespace

    if not vendor_dir.exists():
        return []

    results: list[RewriteResult] = []

    # Process all Python files in the vendor directory
    for py_file in vendor_dir.rglob("*.py"):
        # Rewrite the file in place
        result = rewrite_file(
            py_file,
            py_file,  # Output to same location (in-place rewrite)
            vendored_modules,
            config.vendor_namespace,
            config.core_ap_modules,
        )
        results.append(result)

    return results
