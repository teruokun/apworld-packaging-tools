# External Dependencies in Island Packages

This document explains the current limitations around external dependencies in the island format and provides guidance for developers whose worlds require external resources.

## Overview

The island format specification does **not** currently include a mechanism for declaring external dependencies required for generation. This is an intentional design decision, not an oversight.

## What Are External Dependencies?

External dependencies are resources that a world generator may need but cannot be bundled within the island package itself. Common examples include:

- **Game ROMs**: Required for patch-based randomizers
- **Game binaries**: Executables needed for data extraction
- **Asset files**: Sprites, music, or other game assets
- **Save files**: Base save data for modification
- **Configuration files**: Game-specific settings files

## Why External Dependencies Are Not Specified

### Intellectual Property Concerns

The primary reason external dependencies are not formally specified is **intellectual property (IP) and redistribution concerns**:

1. **Copyright**: Game ROMs, binaries, and assets are typically copyrighted material
2. **Redistribution**: Bundling or hosting these files would constitute unauthorized distribution
3. **Legal liability**: The repository cannot facilitate distribution of copyrighted material
4. **DMCA risk**: Hosting or indexing copyrighted content exposes the project to takedown requests

### Technical Challenges

Beyond legal concerns, there are technical challenges:

1. **Size constraints**: Game binaries can be hundreds of megabytes
2. **Platform variance**: External dependencies may differ by platform
3. **Version variance**: Different game versions may require different resources
4. **Verification complexity**: Validating user-provided files is non-trivial

## Reserved Field for Future Use

The island manifest schema includes a reserved field for future external dependency declarations:

```json
{
  "name": "my-game",
  "version": "1.0.0",
  "external_dependencies": null
}
```

This field is currently:
- **Ignored** by the build tool
- **Not validated** by the manifest schema
- **Reserved** for future specification

When the community reaches consensus on how to specify external resource requirements, this field will be used.

## Recommended Practices

Until a formal specification exists, world developers should follow these practices:

### 1. Document Requirements Clearly

Include a `REQUIREMENTS.md` or dedicated section in your README:

```markdown
## External Requirements

This world requires the following files to generate:

| File | Description | How to Obtain |
|------|-------------|---------------|
| `game.rom` | Game ROM (v1.0 US) | Dump from your own cartridge |
| `base.sav` | Clean save file | Create new game, save at start |

### Obtaining Files

1. **Game ROM**: You must own a legal copy of the game...
2. **Save file**: Start a new game and save immediately...
```

### 2. Provide Hash Verification

Help users verify they have the correct files:

```python
# In your world's __init__.py or setup code
REQUIRED_FILES = {
    "game.rom": {
        "sha256": "abc123...",
        "description": "Game ROM (v1.0 US)",
    },
    "base.sav": {
        "sha256": "def456...",
        "description": "Clean save file",
    },
}

def verify_external_files(path: Path) -> list[str]:
    """Verify required external files exist and match expected hashes."""
    errors = []
    for filename, info in REQUIRED_FILES.items():
        filepath = path / filename
        if not filepath.exists():
            errors.append(f"Missing required file: {filename}")
            continue
        
        actual_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
        if actual_hash != info["sha256"]:
            errors.append(f"Hash mismatch for {filename}")
    
    return errors
```

### 3. Implement Graceful Error Handling

When external resources are missing, provide helpful error messages:

```python
class MyGameWorld(World):
    def generate_early(self) -> None:
        rom_path = self.get_rom_path()
        if not rom_path.exists():
            raise FileNotFoundError(
                f"Game ROM not found at {rom_path}. "
                f"Please see the world documentation for instructions on "
                f"obtaining and placing the required ROM file."
            )
```

### 4. Support Multiple File Locations

Allow users flexibility in where they place external files:

```python
def find_rom(self) -> Path | None:
    """Search for ROM in common locations."""
    search_paths = [
        Path.cwd() / "roms" / "game.rom",
        Path.home() / ".archipelago" / "roms" / "game.rom",
        Path(os.environ.get("GAME_ROM_PATH", "")) if os.environ.get("GAME_ROM_PATH") else None,
    ]
    
    for path in search_paths:
        if path and path.exists():
            return path
    
    return None
```

### 5. Document Version Requirements

Be specific about which versions of external files are supported:

```markdown
## Supported ROM Versions

| Version | Region | SHA256 | Status |
|---------|--------|--------|--------|
| 1.0 | US | `abc123...` | ✅ Fully supported |
| 1.0 | EU | `def456...` | ✅ Fully supported |
| 1.1 | US | `ghi789...` | ⚠️ Partial support |
| 1.0 | JP | `jkl012...` | ❌ Not supported |
```

## Future Considerations

A future specification for external dependencies may include:

### Resource Type Declarations

```json
{
  "external_dependencies": [
    {
      "type": "rom",
      "name": "game.rom",
      "description": "Game ROM (v1.0 US)",
      "sha256": "abc123...",
      "required": true
    }
  ]
}
```

### Platform-Specific Resources

```json
{
  "external_dependencies": [
    {
      "type": "binary",
      "name": "extractor",
      "platforms": {
        "windows": "extractor.exe",
        "linux": "extractor",
        "macos": "extractor"
      }
    }
  ]
}
```

### Optional vs Required Classification

```json
{
  "external_dependencies": [
    {
      "name": "game.rom",
      "required": true,
      "purpose": "generation"
    },
    {
      "name": "music.pak",
      "required": false,
      "purpose": "enhanced_audio"
    }
  ]
}
```

### Legal/Licensing Metadata

```json
{
  "external_dependencies": [
    {
      "name": "game.rom",
      "license_type": "proprietary",
      "redistribution": "prohibited",
      "user_must_own": true
    }
  ]
}
```

## Contributing to the Specification

If you have ideas for how external dependencies should be specified, please:

1. Open an issue in the repository to discuss your proposal
2. Consider the legal implications of any specification
3. Provide concrete use cases from your world development experience
4. Review existing approaches in other packaging ecosystems

The community's input is essential for developing a specification that serves developers while respecting intellectual property rights.
