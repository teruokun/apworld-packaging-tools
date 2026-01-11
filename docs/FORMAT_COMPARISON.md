# Island Format vs Legacy APWorld Format

This document provides a comprehensive comparison between the island format (`.island`) used by this repository and the legacy APWorld format (`.apworld`) used by Archipelago core.

## Quick Comparison Table

| Feature | Legacy APWorld (`.apworld`) | Island Format (`.island`) |
|---------|----------------------------|---------------------------|
| **File Extension** | `.apworld` | `.island` |
| **AP Core Compatible** | ✅ Yes | ❌ No |
| **Entry Points** | Not required | **Required** (`ap-island`) |
| **Platform Tags** | Not supported | Full PEP 425 support |
| **Wheel Metadata** | Partial/None | Full PEP 427 compliance |
| **RECORD File** | Not required | Required with checksums |
| **Dependency Vendoring** | Optional | **Required** |
| **Configuration** | `archipelago.json` | `pyproject.toml` `[tool.island]` |
| **Registry Indexing** | Limited | Full entry point indexing |
| **Search by Game** | Manual tagging | Automatic from entry points |

## Detailed Comparison

### File Extension and Identity

**Legacy APWorld**:
- Uses `.apworld` extension
- Loaded directly by Archipelago core
- Part of the core Archipelago ecosystem

**Island Format**:
- Uses `.island` extension
- Designed for the repository ecosystem
- Clear differentiation from core APWorld format
- NOT compatible with AP core's loading mechanism

### Entry Point Requirements

**Legacy APWorld**:
```
# No entry points required
# WebWorld discovered by convention (worlds/__init__.py)
```

**Island Format**:
```toml
# Required in pyproject.toml
[project.entry-points.ap-island]
my_game = "my_game.world:MyGameWorld"
```

Entry points in island format enable:
- Automatic WebWorld discovery
- Registry indexing and search
- Multiple worlds per package
- Clear API contracts

### Platform Tags

**Legacy APWorld**:
```
my_game-1.0.0.apworld
# No platform information in filename
# Assumes pure Python compatibility
```

**Island Format**:
```
my_game-1.0.0-py3-none-any.island        # Pure Python
my_game-1.0.0-cp311-cp311-macosx_arm64.island  # Platform-specific
```

Platform tags enable:
- Distribution of platform-specific builds
- Automatic selection of compatible variants
- Support for native extensions

### Wheel Metadata Compliance

**Legacy APWorld**:
- May include partial metadata
- No standardized structure
- `archipelago.json` for manifest

**Island Format**:
- Full PEP 427 WHEEL file
- Full PEP 566 METADATA file
- RECORD file with SHA256 checksums
- `entry_points.txt` for entry points
- `island.json` for island-specific metadata

### Package Structure

**Legacy APWorld**:
```
my_game-1.0.0.apworld
└── worlds/my_game/
    ├── __init__.py
    ├── archipelago.json
    └── ...
```

**Island Format**:
```
my_game-1.0.0-py3-none-any.island
├── my_game/
│   ├── __init__.py
│   ├── world.py
│   ├── _vendor/
│   └── ...
└── my_game-1.0.0.dist-info/
    ├── WHEEL
    ├── METADATA
    ├── RECORD
    ├── entry_points.txt
    └── island.json
```

### Configuration Format

**Legacy APWorld** (`archipelago.json`):
```json
{
  "game": "My Game",
  "creator": "Developer",
  "version": "1.0.0",
  "minimum_ap_version": "0.5.0"
}
```

**Island Format** (`pyproject.toml`):
```toml
[project]
name = "my-game"
version = "1.0.0"
description = "My Game for Archipelago"
authors = [{name = "Developer"}]

[project.entry-points.ap-island]
my_game = "my_game.world:MyGameWorld"

[tool.island]
game = "My Game"
minimum_ap_version = "0.5.0"
maximum_ap_version = "0.6.99"

[tool.island.vendor]
exclude = ["typing_extensions"]
```

### Dependency Handling

**Legacy APWorld**:
- Dependencies may or may not be vendored
- No standardized vendoring approach
- Users may need to install dependencies manually

**Island Format**:
- All dependencies **must** be vendored
- Vendored into `_vendor/` directory
- Imports automatically rewritten
- No `Requires-Dist` in METADATA for runtime deps

## Rationale for Differences

### Why a New Extension?

The `.island` extension was chosen to:

1. **Prevent confusion**: Clear distinction from legacy APWorld format
2. **Avoid compatibility assumptions**: Users won't expect island packages to work with AP core
3. **Enable ecosystem evolution**: Repository can evolve independently of AP core constraints
4. **Signal enhanced features**: Different extension indicates different capabilities

### Why Mandatory Entry Points?

Entry points are required because:

1. **Registry indexing**: Enables automatic discovery and search
2. **Multiple worlds**: One package can provide multiple WebWorld implementations
3. **Clear contracts**: Explicit declaration of what the package provides
4. **Future extensibility**: Other entry point types can be added (e.g., `ap-island-client`)

### Why Platform Tags?

Platform tags enable:

1. **Native extensions**: Support for worlds with compiled components
2. **Platform-specific builds**: Different binaries for different platforms
3. **Automatic selection**: Registry returns the most compatible variant
4. **Transparency**: Users know exactly what they're downloading

### Why Mandatory Vendoring?

Vendoring is required because:

1. **Self-containment**: Packages work without additional installation
2. **Isolation**: No conflicts between worlds using different library versions
3. **Reproducibility**: Same package always behaves the same way
4. **Offline support**: No network access needed after download

## Incompatibility with AP Core

**Important**: Island packages are NOT compatible with Archipelago core's APWorld loading mechanism.

### Why Incompatible?

1. **Different structure**: Island packages use wheel structure, not `worlds/` directory
2. **Different extension**: AP core looks for `.apworld`, not `.island`
3. **Different metadata**: AP core expects `archipelago.json`, not `island.json`
4. **Different discovery**: AP core uses convention, island uses entry points

### When to Use Each Format

| Use Case | Recommended Format |
|----------|-------------------|
| Direct AP core integration | Legacy APWorld |
| Repository distribution | Island Format |
| Platform-specific builds | Island Format |
| Multiple WebWorlds per package | Island Format |
| Maximum compatibility | Legacy APWorld |
| Enhanced metadata/search | Island Format |

### Maintaining Both Formats

Developers can maintain both formats if needed:

```
my-game/
├── pyproject.toml           # Island format config
├── src/my_game/
│   ├── __init__.py
│   └── world.py
├── worlds/my_game/          # Legacy APWorld structure
│   ├── __init__.py
│   └── archipelago.json
└── scripts/
    ├── build_island.sh      # Build .island
    └── build_apworld.sh     # Build .apworld
```

## Migration Guide

### From Legacy APWorld to Island

1. **Install the CLI**:
   ```bash
   pip install island-cli
   ```

2. **Run migration**:
   ```bash
   island migrate --from-apworld --generate-pyproject
   ```

3. **Review generated files**:
   - Check `pyproject.toml` for correct metadata
   - Verify `ap-island` entry points are correct
   - Review `[tool.island]` configuration

4. **Build and validate**:
   ```bash
   island build
   island validate
   ```

### What Migration Does

The migration tool:

1. **Converts configuration**: `archipelago.json` → `pyproject.toml`
2. **Detects WebWorlds**: Scans for `World` subclasses
3. **Generates entry points**: Creates `ap-island` entries
4. **Updates imports**: Converts `[tool.apworld]` to `[tool.island]`
5. **Validates result**: Ensures package meets island requirements

### What Migration Does NOT Do

The migration tool does NOT:

1. Make packages compatible with AP core (they become island-only)
2. Modify your source code logic
3. Change your world's behavior
4. Upload to the repository (separate step)

## Relationship to Python Wheels

The island format is based on Python wheels (PEP 427) with extensions:

| Wheel Feature | Island Implementation |
|---------------|----------------------|
| `.whl` extension | `.island` extension |
| `{name}-{version}.dist-info/` | Same structure |
| `WHEEL` file | Same format |
| `METADATA` file | Same format (no Requires-Dist) |
| `RECORD` file | Same format |
| `entry_points.txt` | Same format + `ap-island` group |
| Platform tags | Same PEP 425 format |

The island format adds:
- `island.json` for Archipelago-specific metadata
- Mandatory `ap-island` entry points
- Mandatory dependency vendoring
- No runtime `Requires-Dist` entries

## Future Evolution

The island format may evolve to include:

1. **External dependency specification**: Declaring required external resources
2. **Additional entry point types**: Clients, trackers, etc.
3. **Capability declarations**: Security/sandboxing metadata
4. **Quality signals**: Test coverage, compatibility matrix

These additions will be backward-compatible with existing island packages.
