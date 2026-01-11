# island-cli

CLI tool for Island package development and publishing.

## Installation

```console
pip install island-cli
```

## Quick Start

```bash
# Initialize a new project
island init my-game

# Build distributions
island build

# Validate your package
island validate

# Publish to repository
island publish
```

## Commands

### island init

Initialize a new Island project with scaffolding.

```bash
island init NAME [OPTIONS]
```

Options:
- `--game TEXT` - Display name of the game (defaults to NAME in title case)
- `--author TEXT` - Author name for the package (default: "Your Name")
- `--description TEXT` - Short description of the Island package
- `-o, --output-dir PATH` - Output directory (defaults to current directory)
- `-f, --force` - Overwrite existing files

Creates:
- `pyproject.toml` with `[tool.island]` configuration
- `src/{name}/__init__.py`
- `src/{name}/world.py` with basic World implementation
- `tests/` directory with test scaffolding
- `README.md`
- `LICENSE`
- `docs/setup_en.md`

Examples:
```bash
island init pokemon-emerald
island init my-game --game "My Awesome Game" --author "Developer"
island init zelda --output-dir ./projects
```

### island build

Build Island distribution packages.

```bash
island build [OPTIONS]
```

Options:
- `--sdist/--no-sdist` - Build source distribution (.tar.gz) (default: off)
- `--island/--no-island` - Build binary distribution (.island) (default: on)
- `--vendor/--no-vendor` - Vendor dependencies into .island (default: on)
- `-o, --output-dir PATH` - Output directory (default: "dist")
- `-s, --source-dir PATH` - Source directory (auto-detected)

Examples:
```bash
island build                    # Build .island only
island build --sdist            # Build both .island and .tar.gz
island build --no-vendor        # Build without vendoring dependencies
island build -o ./output        # Output to custom directory
```

### island validate

Validate manifest and package structure.

```bash
island validate [OPTIONS]
```

Options:
- `-m, --manifest PATH` - Path to island.json manifest
- `-p, --pyproject PATH` - Path to pyproject.toml
- `--strict` - Treat warnings as errors
- `--check-structure/--no-check-structure` - Validate package directory structure (default: on)

Examples:
```bash
island validate                     # Validate current project
island validate -m island.json      # Validate specific manifest
island validate --strict            # Treat warnings as errors
```

### island publish

Upload Island packages to the Package Index.

```bash
island publish [OPTIONS]
```

Options:
- `-r, --repository URL` - Package Index URL (default: https://api.archipelago.gg/v1)
- `-t, --token TEXT` - API token for authentication
- `-d, --dist-dir PATH` - Directory containing distributions (default: "dist")
- `-f, --file PATH` - Specific file(s) to upload (can be repeated)
- `--skip-existing` - Skip upload if version already exists
- `--dry-run` - Show what would be uploaded without uploading

Environment variables:
- `ISLAND_TOKEN` or `ARCHIPELAGO_TOKEN` - API token
- `ISLAND_REPOSITORY` - Repository URL

Examples:
```bash
island publish                          # Upload from dist/
island publish -f my_game-1.0.0.island  # Upload specific file
island publish --dry-run                # Preview upload
island publish -r https://custom.repo   # Use custom repository
```

### island migrate

Migrate legacy archipelago.json to modern schema.

```bash
island migrate [OPTIONS]
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
island migrate                          # Migrate in current directory
island migrate -i old/archipelago.json  # Migrate specific file
island migrate --generate-pyproject     # Also create pyproject.toml
island migrate --dry-run                # Preview changes
```

## Global Options

```bash
island [OPTIONS] COMMAND
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
description = "My awesome Island package"

[tool.island]
game = "My Game"
minimum_ap_version = "0.5.0"
maximum_ap_version = "0.6.0"

[tool.island.vendor]
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
| `ISLAND_TOKEN` | API token for publishing |
| `ARCHIPELAGO_TOKEN` | Alternative API token |
| `ISLAND_REPOSITORY` | Default repository URL |

## Workflow Example

Complete workflow for creating and publishing an Island package:

```bash
# 1. Initialize project
island init pokemon-emerald --author "Your Name"
cd pokemon_emerald

# 2. Implement your world
# Edit src/pokemon_emerald/world.py

# 3. Validate
island validate

# 4. Build
island build --sdist

# 5. Test locally
# Copy dist/*.island to Archipelago/worlds/

# 6. Publish
export ISLAND_TOKEN="your-api-token"
island publish
```

## License

MIT License
