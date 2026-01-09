# apworld-cli

CLI tool for APWorld package development and publishing.

## Installation

```console
pip install apworld-cli
```

## Quick Start

```bash
# Initialize a new project
apworld init my-game

# Build distributions
apworld build

# Validate your package
apworld validate

# Publish to repository
apworld publish
```

## Commands

### apworld init

Initialize a new APWorld project with scaffolding.

```bash
apworld init NAME [OPTIONS]
```

Options:
- `--game TEXT` - Display name of the game (defaults to NAME in title case)
- `--author TEXT` - Author name for the package (default: "Your Name")
- `--description TEXT` - Short description of the APWorld
- `-o, --output-dir PATH` - Output directory (defaults to current directory)
- `-f, --force` - Overwrite existing files

Creates:
- `pyproject.toml` with `[tool.apworld]` configuration
- `src/{name}/__init__.py`
- `src/{name}/world.py` with basic World implementation
- `tests/` directory with test scaffolding
- `README.md`
- `LICENSE`
- `docs/setup_en.md`

Examples:
```bash
apworld init pokemon-emerald
apworld init my-game --game "My Awesome Game" --author "Developer"
apworld init zelda --output-dir ./projects
```

### apworld build

Build APWorld distribution packages.

```bash
apworld build [OPTIONS]
```

Options:
- `--sdist/--no-sdist` - Build source distribution (.tar.gz) (default: off)
- `--apworld/--no-apworld` - Build binary distribution (.apworld) (default: on)
- `--vendor/--no-vendor` - Vendor dependencies into .apworld (default: on)
- `-o, --output-dir PATH` - Output directory (default: "dist")
- `-s, --source-dir PATH` - Source directory (auto-detected)

Examples:
```bash
apworld build                    # Build .apworld only
apworld build --sdist            # Build both .apworld and .tar.gz
apworld build --no-vendor        # Build without vendoring dependencies
apworld build -o ./output        # Output to custom directory
```

Output:
```
Building from: src/my_game
Output directory: dist

Building binary distribution (.apworld)...
  Vendoring dependencies...
  Created: my_game-1.0.0-py3-none-any.apworld (12,345 bytes)
  Files included: 15
  Platform: py3-none-any
  Pure Python: True

Build complete! 1 distribution(s) created.
```

### apworld validate

Validate manifest and package structure.

```bash
apworld validate [OPTIONS]
```

Options:
- `-m, --manifest PATH` - Path to archipelago.json manifest
- `-p, --pyproject PATH` - Path to pyproject.toml
- `--strict` - Treat warnings as errors
- `--check-structure/--no-check-structure` - Validate package directory structure (default: on)

Validates:
- JSON/TOML syntax
- Manifest schema compliance
- Semantic version format
- Required fields (game, version, compatible_version)
- Package directory structure

Examples:
```bash
apworld validate                     # Validate current project
apworld validate -m archipelago.json # Validate specific manifest
apworld validate --strict            # Treat warnings as errors
```

Output:
```
Validating: pyproject.toml
  Transformed to manifest successfully
  Validating manifest schema...
  Manifest schema: valid
  Checking package structure...

Validation passed!
```

### apworld publish

Upload APWorld packages to the Package Index.

```bash
apworld publish [OPTIONS]
```

Options:
- `-r, --repository URL` - Package Index URL (default: https://api.archipelago.gg/v1)
- `-t, --token TEXT` - API token for authentication
- `-d, --dist-dir PATH` - Directory containing distributions (default: "dist")
- `-f, --file PATH` - Specific file(s) to upload (can be repeated)
- `--skip-existing` - Skip upload if version already exists
- `--dry-run` - Show what would be uploaded without uploading

Environment variables:
- `APWORLD_TOKEN` or `ARCHIPELAGO_TOKEN` - API token
- `APWORLD_REPOSITORY` - Repository URL

Examples:
```bash
apworld publish                          # Upload from dist/
apworld publish -f my_game-1.0.0.apworld # Upload specific file
apworld publish --dry-run                # Preview upload
apworld publish -r https://custom.repo   # Use custom repository
apworld publish --skip-existing          # Skip if version exists
```

Output:
```
Repository: https://api.archipelago.gg/v1
Distributions to upload: 1
  - my_game-1.0.0-py3-none-any.apworld (12,345 bytes)

Uploading: my_game-1.0.0-py3-none-any.apworld
  SHA256: abc123...
  Uploaded successfully!

Published 1 distribution(s) successfully!
```

### apworld migrate

Migrate legacy archipelago.json to modern schema.

```bash
apworld migrate [OPTIONS]
```

Options:
- `-i, --input PATH` - Path to legacy archipelago.json (defaults to current directory)
- `-o, --output PATH` - Output path for migrated manifest (defaults to overwriting input)
- `--generate-pyproject` - Also generate a pyproject.toml file
- `--pyproject-output PATH` - Output path for pyproject.toml
- `--dry-run` - Show what would be generated without writing files
- `-f, --force` - Overwrite existing files

Examples:
```bash
apworld migrate                          # Migrate in current directory
apworld migrate -i old/archipelago.json  # Migrate specific file
apworld migrate --generate-pyproject     # Also create pyproject.toml
apworld migrate --dry-run                # Preview changes
```

Output:
```
Reading: archipelago.json
Migrating to modern schema...
  Migration successful!
Wrote: archipelago.json
Wrote: pyproject.toml

Migration complete!

Next steps:
  1. Review and customize pyproject.toml
  2. Run 'apworld validate' to verify
  3. Run 'apworld build' to create distributions
```

## Global Options

```bash
apworld [OPTIONS] COMMAND
```

Options:
- `-v, --verbose` - Enable verbose output
- `-C, --directory PATH` - Change to directory before running command
- `--version` - Show version and exit
- `--help` - Show help message

## Configuration

The CLI reads configuration from `pyproject.toml`:

```toml
[project]
name = "my-game"
version = "1.0.0"
description = "My awesome APWorld"

[tool.apworld]
game = "My Game"
minimum_ap_version = "0.5.0"
maximum_ap_version = "0.6.0"

[tool.apworld.vendor]
exclude = ["typing_extensions"]
```

For legacy projects, the CLI also supports `archipelago.json`:

```json
{
    "game": "My Game",
    "version": 1,
    "compatible_version": 1,
    "world_version": "1.0.0",
    "minimum_ap_version": "0.5.0"
}
```

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (configuration, validation, build, or upload failure) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `APWORLD_TOKEN` | API token for publishing |
| `ARCHIPELAGO_TOKEN` | Alternative API token |
| `APWORLD_REPOSITORY` | Default repository URL |

## Workflow Example

Complete workflow for creating and publishing an APWorld:

```bash
# 1. Initialize project
apworld init pokemon-emerald --author "Your Name"
cd pokemon_emerald

# 2. Implement your world
# Edit src/pokemon_emerald/world.py

# 3. Validate
apworld validate

# 4. Build
apworld build --sdist

# 5. Test locally
# Copy dist/*.apworld to Archipelago/worlds/

# 6. Publish
export APWORLD_TOKEN="your-api-token"
apworld publish
```

## License

MIT License
