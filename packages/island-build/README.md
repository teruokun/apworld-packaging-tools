# island-build

Distribution building for Island packages (.island, .tar.gz).

## Installation

```console
pip install island-build
```

## Overview

This package provides utilities for building Island distributions:
- Binary distributions (`.island`) - ZIP archives with compiled code and vendored dependencies
- Source distributions (`.tar.gz`) - archives with source files
- PEP 427 wheel naming conventions for filenames

## Quick Start

```python
from island_build import build_island, build_sdist, BuildConfig

# Load configuration from pyproject.toml
config = BuildConfig.from_pyproject("pyproject.toml")

# Build binary distribution (.island)
result = build_island(config, output_dir="dist/")
print(f"Created: {result.path}")  # dist/my_game-1.0.0-py3-none-any.island

# Build source distribution (.tar.gz)
result = build_sdist(config, output_dir="dist/")
print(f"Created: {result.path}")  # dist/my_game-1.0.0.tar.gz
```

## API Reference

### BuildConfig

Configuration for building Island packages.

```python
from island_build import BuildConfig

# Load from pyproject.toml
config = BuildConfig.from_pyproject("path/to/pyproject.toml")

# Access configuration
config.name              # Package name
config.version           # Package version
config.game_name         # Game display name
config.source_dir        # Source directory path
config.include_patterns  # Glob patterns for files to include
config.exclude_patterns  # Glob patterns for files to exclude
config.dependencies      # List of dependencies to vendor
config.vendor_exclude    # Packages to exclude from vendoring
```

### build_island()

Build a binary distribution (.island) file.

```python
from island_build import build_island, BuildConfig, PlatformTag

config = BuildConfig.from_pyproject("pyproject.toml")

result = build_island(
    config,
    output_dir="dist/",
    source_dir=None,       # Optional: override source directory
    vendor_dir=None,       # Optional: pre-vendored dependencies
    platform_tag=None,     # Optional: override platform tag
)

# Result attributes
result.path            # Path to created .island file
result.filename        # Filename of created archive
result.files_included  # List of files in archive
result.manifest        # Generated island.json content
result.size            # Archive size in bytes
result.is_pure_python  # True if no native extensions
result.platform_tag    # Platform tag used
```

### build_island_with_vendoring()

Build an Island with automatic dependency vendoring.

```python
from island_build import build_island_with_vendoring, BuildConfig

config = BuildConfig.from_pyproject("pyproject.toml")

# Automatically vendors dependencies and rewrites imports
result = build_island_with_vendoring(
    config,
    output_dir="dist/",
    source_dir=None,     # Optional: override source directory
    platform_tag=None,   # Optional: override platform tag
)
```

### build_sdist()

Build a source distribution (.tar.gz) file.

```python
from island_build import build_sdist, BuildConfig

config = BuildConfig.from_pyproject("pyproject.toml")

result = build_sdist(
    config,
    output_dir="dist/",
    source_dir=None,  # Optional: override source directory
)

# Result attributes
result.path            # Path to created .tar.gz file
result.filename        # Filename of created archive
result.files_included  # List of files in archive
result.size            # Archive size in bytes
```

### build_sdist_from_directory()

Build a source distribution without a BuildConfig.

```python
from island_build import build_sdist_from_directory

result = build_sdist_from_directory(
    source_dir="src/my_game/",
    name="my-game",
    version="1.0.0",
    output_dir="dist/",
    include_patterns=["*.py", "**/*.py"],  # Optional
    exclude_patterns=["__pycache__"],       # Optional
)
```

### collect_source_files()

Collect source files matching patterns.

```python
from pathlib import Path
from island_build import collect_source_files

files = collect_source_files(
    source_dir=Path("src/my_game/"),
    include_patterns=["*.py", "**/*.py"],
    exclude_patterns=["__pycache__", "*.pyc"],
    include_files=["README.md", "LICENSE"],
)
# Returns list of Path objects relative to source_dir
```

## Filename Utilities

### PlatformTag

Represents a platform compatibility tag (PEP 425).

```python
from island_build import PlatformTag, UNIVERSAL_TAG

# Universal tag for pure Python
tag = UNIVERSAL_TAG  # py3-none-any

# Create custom tag
tag = PlatformTag(python="cp311", abi="cp311", platform="win_amd64")

# Parse from string
tag = PlatformTag.from_string("py3-none-any")

# Convert to string
str(tag)  # "py3-none-any"
```

### Pre-defined Platform Tags

```python
from island_build import (
    UNIVERSAL_TAG,      # py3-none-any (pure Python)
    WINDOWS_X64_TAG,    # cp311-cp311-win_amd64
    WINDOWS_ARM64_TAG,  # cp311-cp311-win_arm64
    MACOS_X64_TAG,      # cp311-cp311-macosx_11_0_x86_64
    MACOS_ARM64_TAG,    # cp311-cp311-macosx_11_0_arm64
    LINUX_X64_TAG,      # cp311-cp311-manylinux_2_17_x86_64
    LINUX_ARM64_TAG,    # cp311-cp311-manylinux_2_17_aarch64
)
```

### build_island_filename()

Generate an Island filename following PEP 427 conventions.

```python
from island_build import build_island_filename, UNIVERSAL_TAG

filename = build_island_filename("pokemon-emerald", "1.0.0")
# "pokemon_emerald-1.0.0-py3-none-any.island"

filename = build_island_filename("my-game", "2.0.0-alpha.1", UNIVERSAL_TAG)
# "my_game-2.0.0_alpha.1-py3-none-any.island"
```

### build_sdist_filename()

Generate a source distribution filename.

```python
from island_build import build_sdist_filename

filename = build_sdist_filename("pokemon-emerald", "1.0.0")
# "pokemon_emerald-1.0.0.tar.gz"
```

### parse_island_filename()

Parse an Island filename into components.

```python
from island_build import parse_island_filename

parsed = parse_island_filename("pokemon_emerald-1.0.0-py3-none-any.island")
parsed.name     # "pokemon_emerald"
parsed.version  # "1.0.0"
parsed.tag      # PlatformTag(python="py3", abi="none", platform="any")
```

### parse_sdist_filename()

Parse a source distribution filename.

```python
from island_build import parse_sdist_filename

parsed = parse_sdist_filename("pokemon_emerald-1.0.0.tar.gz")
parsed.name     # "pokemon_emerald"
parsed.version  # "1.0.0"
```

### normalize_name() / normalize_version()

Normalize names and versions for filenames.

```python
from island_build import normalize_name, normalize_version

normalize_name("Pokemon-Emerald")   # "pokemon_emerald"
normalize_name("my.game.world")     # "my_game_world"

normalize_version("1.0.0-alpha.1")  # "1.0.0_alpha.1"
normalize_version("2.0.0+build")    # "2.0.0+build"
```

### is_pure_python_tag()

Check if a platform tag indicates pure Python.

```python
from island_build import is_pure_python_tag, UNIVERSAL_TAG, WINDOWS_X64_TAG

is_pure_python_tag(UNIVERSAL_TAG)    # True
is_pure_python_tag(WINDOWS_X64_TAG)  # False
```

## Default Patterns

```python
from island_build import DEFAULT_INCLUDE_PATTERNS, DEFAULT_EXCLUDE_PATTERNS

# Default include patterns
DEFAULT_INCLUDE_PATTERNS = ["*.py", "**/*.py"]

# Default exclude patterns (partial list)
DEFAULT_EXCLUDE_PATTERNS = [
    "__pycache__", "*.pyc", "*.pyo",
    ".git", ".gitignore",
    ".pytest_cache", ".mypy_cache",
    "*.egg-info", "dist", "build",
    ".venv", "venv", ...
]
```

## Exceptions

```python
from island_build import IslandError, SdistError, FilenameError, BuildConfigError

# IslandError - raised when Island building fails
# SdistError - raised when source distribution building fails
# FilenameError - raised when filename generation/parsing fails
# BuildConfigError - raised when configuration is invalid
```

## Island Archive Structure

The `.island` file is a ZIP archive with this structure:

```
{package_name}/
├── __init__.py
├── ... (source files)
├── _vendor/
│   └── ... (vendored dependencies)
└── island.json
```

## License

MIT License
