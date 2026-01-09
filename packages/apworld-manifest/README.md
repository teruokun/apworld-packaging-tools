# apworld-manifest

Manifest schema, validation, and transformation for APWorld packages.

## Installation

```console
pip install apworld-manifest
```

## Features

- JSON Schema validation for `archipelago.json`
- Transform `pyproject.toml` to `archipelago.json`
- Support for PEP 621 project metadata
- APWorld-specific configuration via `[tool.apworld]`
- Backward compatible with existing APWorld manifests
- Structured error reporting

## API Reference

### Validation

#### validate_manifest(manifest)

Validate an archipelago.json manifest against the schema.

```python
from apworld_manifest import validate_manifest

manifest = {
    "game": "Pokemon Emerald",
    "version": 7,
    "compatible_version": 5,
    "world_version": "1.0.0"
}

result = validate_manifest(manifest)
print(result.valid)      # True
print(result.errors)     # []
print(result.manifest)   # Manifest with defaults applied
```

#### validate_manifest_strict(manifest)

Validate and raise an exception if invalid.

```python
from apworld_manifest import validate_manifest_strict, ManifestValidationError

try:
    manifest = validate_manifest_strict({"game": "Test"})  # Missing required fields
except ManifestValidationError as e:
    for error in e.errors:
        print(f"{error.field}: {error.message}")
```

#### ValidationResult

Result of manifest validation.

```python
@dataclass
class ValidationResult:
    valid: bool                          # Whether the manifest is valid
    errors: list[ValidationErrorDetail]  # List of validation errors
    manifest: dict | None                # Validated manifest with defaults (None if invalid)
```

#### ValidationErrorDetail

Details about a single validation error.

```python
@dataclass
class ValidationErrorDetail:
    field: str      # JSON path to the invalid field (e.g., "world_version")
    message: str    # Human-readable error message
    value: Any      # The invalid value (if available)
```

### Transformation

#### transform_pyproject(pyproject_path)

Transform a pyproject.toml file into an archipelago.json manifest.

```python
from apworld_manifest import transform_pyproject

manifest = transform_pyproject("path/to/pyproject.toml")
print(manifest["game"])           # "Pokemon Emerald"
print(manifest["world_version"])  # "2.1.0"
```

#### transform_pyproject_dict(pyproject)

Transform a parsed pyproject.toml dictionary.

```python
from apworld_manifest import transform_pyproject_dict

pyproject = {
    "project": {
        "name": "pokemon-emerald",
        "version": "2.1.0",
        "description": "Pokemon Emerald for Archipelago",
        "authors": [{"name": "Zunawe"}],
    },
    "tool": {
        "apworld": {
            "game": "Pokemon Emerald",
            "minimum_ap_version": "0.5.0",
        }
    }
}

manifest = transform_pyproject_dict(pyproject)
```

#### TransformConfig

Configuration for transformation.

```python
from apworld_manifest import TransformConfig, transform_pyproject

config = TransformConfig(
    schema_version=7,      # APContainer schema version
    compatible_version=5,  # Minimum compatible version
)

manifest = transform_pyproject("pyproject.toml", config)
```

### Schema Constants

```python
from apworld_manifest import (
    MANIFEST_SCHEMA,           # Full JSON Schema definition
    MANIFEST_DEFAULTS,         # Default values for optional fields
    CURRENT_SCHEMA_VERSION,    # Current schema version (7)
    MIN_COMPATIBLE_VERSION,    # Minimum compatible version (5)
    PLATFORMS,                 # Valid platform values
    SEMVER_PATTERN,            # Regex pattern for semver validation
)
```

## Manifest Schema

The `archipelago.json` manifest follows this schema:

```json
{
  "game": "Pokemon Emerald",
  "version": 7,
  "compatible_version": 5,
  "world_version": "2.1.0",
  "minimum_ap_version": "0.5.0",
  "maximum_ap_version": "0.6.99",
  "authors": ["Zunawe"],
  "description": "Pokemon Emerald randomizer for Archipelago",
  "license": "MIT",
  "homepage": "https://github.com/ArchipelagoMW/Archipelago",
  "repository": "https://github.com/ArchipelagoMW/Archipelago",
  "keywords": ["pokemon", "gba", "emerald"],
  "platforms": ["windows", "macos", "linux"],
  "pure_python": true
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `game` | string | Display name of the game |
| `version` | integer | APContainer schema version (must be 7) |
| `compatible_version` | integer | Minimum compatible schema version (5-7) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `world_version` | string | - | Package version (semver format) |
| `minimum_ap_version` | string | - | Minimum Core AP version |
| `maximum_ap_version` | string | - | Maximum Core AP version |
| `authors` | array | `[]` | List of author names |
| `description` | string | `""` | Package description (max 500 chars) |
| `license` | string | `""` | License identifier |
| `homepage` | string | - | Homepage URL |
| `repository` | string | - | Repository URL |
| `keywords` | array | `[]` | Search keywords |
| `platforms` | array | `["windows", "macos", "linux"]` | Supported platforms |
| `pure_python` | boolean | `true` | Whether package is pure Python |

## pyproject.toml Configuration

Configure your APWorld using standard PEP 621 metadata plus `[tool.apworld]`:

```toml
[project]
name = "pokemon-emerald"
version = "2.1.0"
description = "Pokemon Emerald randomizer for Archipelago"
readme = "README.md"
license = {text = "MIT"}
authors = [{name = "Zunawe", email = "zunawe@example.com"}]
keywords = ["pokemon", "gba", "emerald", "randomizer"]
requires-python = ">=3.10"
dependencies = ["pyyaml>=6.0"]

[project.urls]
Homepage = "https://github.com/ArchipelagoMW/Archipelago"
Repository = "https://github.com/ArchipelagoMW/Archipelago"

[tool.apworld]
game = "Pokemon Emerald"
minimum_ap_version = "0.5.0"
maximum_ap_version = "0.6.99"
platforms = ["windows", "macos", "linux"]
pure_python = true

[tool.apworld.vendor]
exclude = ["typing_extensions", "colorama"]
```

### Field Mapping

| pyproject.toml | archipelago.json |
|----------------|------------------|
| `project.name` | `game` (title-cased if `tool.apworld.game` not set) |
| `project.version` | `world_version` |
| `project.description` | `description` |
| `project.authors[].name` | `authors` |
| `project.license.text` | `license` |
| `project.keywords` | `keywords` |
| `project.urls.Homepage` | `homepage` |
| `project.urls.Repository` | `repository` |
| `tool.apworld.game` | `game` |
| `tool.apworld.minimum_ap_version` | `minimum_ap_version` |
| `tool.apworld.maximum_ap_version` | `maximum_ap_version` |
| `tool.apworld.platforms` | `platforms` |
| `tool.apworld.pure_python` | `pure_python` |

## Exceptions

```python
from apworld_manifest import (
    ManifestError,           # Base exception
    ManifestValidationError, # Validation failed
    ManifestTransformError,  # Transformation failed
)
```

## License

MIT License
