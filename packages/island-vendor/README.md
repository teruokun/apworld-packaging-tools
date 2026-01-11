# island-vendor

Dependency vendoring and import rewriting for Island packages.

## Installation

```console
pip install island-vendor
```

## Features

- AST-based import transformation
- Download and vendor Python dependencies
- Rewrite imports to use vendored namespace
- Preserve Core AP imports unchanged
- Track vendored package versions

## Overview

Island packages need to be self-contained, bundling their dependencies to avoid conflicts with other Islands or Core Archipelago. This package provides:

1. **Dependency Vendoring**: Download and extract dependencies into a `_vendor` directory
2. **Import Rewriting**: Transform imports to use the vendored namespace

## API Reference

### Configuration

#### VendorConfig

Configuration for dependency vendoring.

```python
from island_vendor import VendorConfig

# Create from pyproject.toml
config = VendorConfig.from_pyproject("pyproject.toml")

# Or create manually
config = VendorConfig(
    package_name="my_game",
    dependencies=["pyyaml>=6.0", "requests"],
    exclude=["typing_extensions"],  # Don't vendor these
    namespace="_vendor",            # Vendor directory name
)

# Properties
print(config.vendor_namespace)  # "my_game._vendor"
print(config.core_ap_modules)   # frozenset of Core AP modules
```

#### VendorConfig.from_pyproject(path)

Load configuration from pyproject.toml.

```python
config = VendorConfig.from_pyproject("pyproject.toml")
```

Reads from `[tool.island.vendor]` section:

```toml
[project]
name = "my-game"
dependencies = ["pyyaml>=6.0", "requests"]

[tool.island.vendor]
exclude = ["typing_extensions", "colorama"]
namespace = "_vendor"
```

### Vendoring Dependencies

#### vendor_dependencies(config, target_dir)

Download and vendor dependencies into a target directory.

```python
from island_vendor import VendorConfig, vendor_dependencies

config = VendorConfig(
    package_name="my_game",
    dependencies=["pyyaml>=6.0"],
)

result = vendor_dependencies(config, target_dir="build/_vendor")

# Check results
print(result.packages)  # List of VendoredPackage
print(result.errors)    # List of error messages
print(result.get_vendored_module_names())  # {"yaml"}
```

#### VendorResult

Result of vendoring operation.

```python
@dataclass
class VendorResult:
    target_dir: Path                    # Where packages were vendored
    packages: list[VendoredPackage]     # Successfully vendored packages
    errors: list[str]                   # Error messages

    def get_vendored_module_names(self) -> set[str]:
        """Get all top-level module names that were vendored."""
```

#### VendoredPackage

Information about a vendored package.

```python
@dataclass
class VendoredPackage:
    name: str                    # Package name (e.g., "pyyaml")
    version: str                 # Package version
    source_path: Path            # Path where package was extracted
    top_level_modules: list[str] # Top-level module names (e.g., ["yaml"])
```

#### create_vendor_manifest(result, output_path)

Create a JSON manifest of vendored packages.

```python
from island_vendor import vendor_dependencies, create_vendor_manifest

result = vendor_dependencies(config, "build/_vendor")
create_vendor_manifest(result, "build/_vendor/manifest.json")
```

Output:
```json
{
  "vendored_packages": {
    "pyyaml": {
      "version": "6.0.1",
      "modules": ["yaml"]
    }
  }
}
```

### Import Rewriting

#### rewrite_imports(source_dir, output_dir, vendored_modules, config)

Rewrite imports in all Python files in a directory.

```python
from island_vendor import VendorConfig, vendor_dependencies, rewrite_imports

config = VendorConfig(package_name="my_game", dependencies=["pyyaml"])
result = vendor_dependencies(config, "build/_vendor")

# Rewrite imports in source files
rewrite_results = rewrite_imports(
    source_dir="src/my_game",
    output_dir="build/my_game",
    vendored_modules=result.get_vendored_module_names(),
    config=config,
)

for r in rewrite_results:
    print(f"{r.source_path}: {r.imports_rewritten} rewritten, {r.imports_preserved} preserved")
```

#### rewrite_file(source_path, output_path, vendored_modules, vendor_namespace, core_ap_modules)

Rewrite imports in a single file.

```python
from island_vendor import rewrite_file, CORE_AP_MODULES

result = rewrite_file(
    source_path=Path("src/my_game/main.py"),
    output_path=Path("build/my_game/main.py"),
    vendored_modules={"yaml", "requests"},
    vendor_namespace="my_game._vendor",
    core_ap_modules=CORE_AP_MODULES,
)
```

#### rewrite_source(source, vendored_modules, vendor_namespace, core_ap_modules)

Rewrite imports in source code string.

```python
from island_vendor import rewrite_source, CORE_AP_MODULES

source = """
import yaml
from BaseClasses import Item
from requests import get
"""

rewritten, num_rewritten, num_preserved = rewrite_source(
    source,
    vendored_modules={"yaml", "requests"},
    vendor_namespace="my_game._vendor",
    core_ap_modules=CORE_AP_MODULES,
)

print(rewritten)
# from my_game._vendor import yaml
# from BaseClasses import Item
# from my_game._vendor.requests import get
```

#### RewriteResult

Result of rewriting a single file.

```python
@dataclass
class RewriteResult:
    source_path: Path       # Original source file
    output_path: Path       # Output file
    imports_rewritten: int  # Number of imports rewritten
    imports_preserved: int  # Number of imports preserved (Core AP)
    modified: bool          # Whether the file was modified
```

### Core AP Modules

The `CORE_AP_MODULES` constant contains module names that should never be rewritten:

```python
from island_vendor import CORE_AP_MODULES

print(CORE_AP_MODULES)
# frozenset({'BaseClasses', 'Options', 'worlds', 'NetUtils', ...})
```

These modules are part of Core Archipelago and should be imported normally.

## Import Transformation Examples

### Before Rewriting

```python
import yaml
from yaml import safe_load
from pydantic import BaseModel
from BaseClasses import Item, Location
from worlds.generic import Rules
```

### After Rewriting (for package "my_game")

```python
from my_game._vendor import yaml
from my_game._vendor.yaml import safe_load
from my_game._vendor.pydantic import BaseModel
from BaseClasses import Item, Location  # Preserved
from worlds.generic import Rules        # Preserved
```

## Complete Workflow Example

```python
from pathlib import Path
from island_vendor import (
    VendorConfig,
    vendor_dependencies,
    rewrite_imports,
    create_vendor_manifest,
)

# 1. Configure vendoring
config = VendorConfig.from_pyproject("pyproject.toml")

# 2. Vendor dependencies
vendor_result = vendor_dependencies(
    config,
    target_dir="build/_vendor",
)

if vendor_result.errors:
    print("Errors:", vendor_result.errors)

# 3. Create vendor manifest
create_vendor_manifest(vendor_result, "build/_vendor/manifest.json")

# 4. Rewrite imports in source files
rewrite_results = rewrite_imports(
    source_dir="src/my_game",
    output_dir="build/my_game",
    vendored_modules=vendor_result.get_vendored_module_names(),
    config=config,
)

# 5. Copy vendor directory to build output
import shutil
shutil.copytree("build/_vendor", "build/my_game/_vendor")

print(f"Vendored {len(vendor_result.packages)} packages")
print(f"Rewrote imports in {len(rewrite_results)} files")
```

## Exceptions

```python
from island_vendor import (
    VendorConfigError,        # Configuration error
    DependencyDownloadError,  # Failed to download dependency
    VendorPackageError,       # Failed to vendor package
    ImportRewriteError,       # Failed to rewrite imports
)
```

## License

MIT License
