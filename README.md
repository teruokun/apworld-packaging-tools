# archipelago-repository

Island packaging and registry tools for the Archipelago multiworld randomizer ecosystem.

**Note: Currently, all of the code in this repository is generated using AI. While the workflow is a multi-phase process designed to ensure quality, please review carefully.**

## Overview

This monorepo provides a complete toolchain for building, validating, and registering island packages (`.island`):

- **Build Tools**: Create `.island` binary distributions and `.tar.gz` source distributions
- **Package Registry API**: Index and discover island packages with search, versioning, and authentication
- **CLI**: Developer-friendly commands for the full package lifecycle

The **island format** is a Python wheel extension specifically designed for Archipelago game worlds, with mandatory entry points, vendored dependencies, and platform-specific distribution support.

### Registry Model

The repository operates as a **registry** rather than a package host—similar to Go's module proxy model:

- **Registry stores**: Package metadata, external URLs, and SHA256 checksums
- **Registry does NOT store**: Actual package files (`.island`, `.tar.gz`)
- **Packages hosted on**: GitHub Releases or other external services
- **Clients download from**: External URLs directly, verifying checksums locally

## Packages

| Package | Description | Install |
|---------|-------------|---------|
| [island-version](packages/island-version/) | Semantic version parsing and comparison | `pip install island-version` |
| [island-manifest](packages/island-manifest/) | Manifest schema, validation, transformation | `pip install island-manifest` |
| [island-vendor](packages/island-vendor/) | Dependency vendoring and import rewriting | `pip install island-vendor` |
| [island-build](packages/island-build/) | Distribution building (.island, .tar.gz) | `pip install island-build` |
| [island-api](packages/island-api/) | Registry server (FastAPI) | `pip install island-api` |
| [island-cli](packages/island-cli/) | CLI tool for developers | `pip install island-cli` |

## Quick Start

### For World Developers

Install the CLI tool to build and register your island package:

```console
pip install island-cli
```

#### Initialize a New Project

```console
island init my-game
cd my-game
```

This creates a project structure with:
- `pyproject.toml` - Project configuration with `[tool.island]` section
- `src/my_game/` - Source code directory
- `tests/` - Test directory
- Required `ap-island` entry points

#### Configure Your Island Package

Edit `pyproject.toml` to configure your island package:

```toml
[project]
name = "my-game"
version = "1.0.0"
description = "My awesome game for Archipelago"
authors = [{name = "Your Name", email = "you@example.com"}]
keywords = ["rpg", "adventure"]
license = {text = "MIT"}

[project.urls]
Homepage = "https://github.com/you/my-game"
Repository = "https://github.com/you/my-game"

# Required: at least one ap-island entry point
[project.entry-points.ap-island]
my_game = "my_game.world:MyGameWorld"

[tool.island]
game = "My Game"
minimum_ap_version = "0.5.0"
maximum_ap_version = "0.6.99"

[tool.island.vendor]
exclude = ["typing_extensions"]
```

#### Build Your Island Package

```console
# Build both source and binary distributions
island build

# Build only the .island binary
island build --island

# Build only the source distribution
island build --sdist
```

Output files are placed in `dist/`:
- `my_game-1.0.0-py3-none-any.island` - Binary distribution
- `my_game-1.0.0.tar.gz` - Source distribution

#### Validate Your Package

```console
island validate
```

This checks:
- Manifest schema compliance
- Version format (semantic versioning)
- Package structure
- Required `ap-island` entry points
- Required files

#### Register with the Registry

Register your package by providing URLs to externally-hosted assets (e.g., GitHub Releases):

```console
# Register with checksum computed from local file
island register \
    --url https://github.com/user/repo/releases/download/v1.0.0/my_game-1.0.0-py3-none-any.island \
    --file dist/my_game-1.0.0-py3-none-any.island \
    --token YOUR_API_TOKEN

# Register multiple distributions
island register \
    --url https://github.com/.../my_game-1.0.0-py3-none-any.island \
    --file dist/my_game-1.0.0-py3-none-any.island \
    --url https://github.com/.../my_game-1.0.0.tar.gz \
    --file dist/my_game-1.0.0.tar.gz

# Dry run to see the registration payload
island register \
    --url https://github.com/.../my_game-1.0.0-py3-none-any.island \
    --file dist/my_game-1.0.0-py3-none-any.island \
    --dry-run
```

The registry will:
1. Verify each URL is accessible (HTTPS only)
2. Download and verify the SHA256 checksum matches
3. Store the metadata and external URL (not the file itself)

#### Install Packages

Install packages from the registry (downloads from external URL, verifies checksum):

```console
# Install latest version
island install my-game

# Install specific version
island install my-game --version 1.0.0

# Install to specific directory
island install my-game --output ./packages
```

The client:
1. Queries the registry for package metadata
2. Downloads directly from the external URL (e.g., GitHub Releases)
3. Verifies the SHA256 checksum matches the registry-provided value
4. Rejects the download if verification fails

#### Migrate Legacy Projects

If you have an existing APWorld with `archipelago.json` or `[tool.apworld]` configuration:

```console
# Migrate from legacy APWorld format
island migrate --from-apworld

# Also generate pyproject.toml
island migrate --generate-pyproject
```

The migration tool:
- Converts `[tool.apworld]` to `[tool.island]`
- Detects WebWorld classes and generates `ap-island` entry points
- Preserves all existing metadata
- Validates the result

### For Repository Operators

Install and run the API server:

```console
pip install island-api
```

#### Basic Setup

```console
# Run with default SQLite database
uvicorn island_api:app --host 0.0.0.0 --port 8000
```

#### Production Configuration

Configure via environment variables:

```bash
# Database
export ISLAND_DATABASE_URL="postgresql://user:pass@localhost/island"

# Rate limiting
export ISLAND_RATE_LIMIT_ENABLED="true"
export ISLAND_RATE_LIMIT_RPM="100"

# OIDC for Trusted Publishers
export ISLAND_OIDC_ENABLED="true"
export ISLAND_OIDC_ISSUER="https://token.actions.githubusercontent.com"

uvicorn island_api:app --host 0.0.0.0 --port 8000
```

#### Using Docker

```dockerfile
FROM python:3.11-slim
RUN pip install island-api uvicorn
EXPOSE 8000
CMD ["uvicorn", "island_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### API Usage Examples

#### Search Packages

```bash
# List all packages
curl https://api.example.com/v1/island/packages

# Search by keyword
curl "https://api.example.com/v1/island/search?q=pokemon"

# Filter by game
curl "https://api.example.com/v1/island/search?game=Pokemon%20Emerald"

# Filter by entry point
curl "https://api.example.com/v1/island/search?entry_point=pokemon_emerald"

# Filter by Core AP compatibility
curl "https://api.example.com/v1/island/search?compatible_with=0.5.0"

# Filter by platform
curl "https://api.example.com/v1/island/search?platform=macosx_arm64"
```

#### Get Package Information

```bash
# Get package metadata
curl https://api.example.com/v1/island/packages/pokemon-emerald

# List all versions
curl https://api.example.com/v1/island/packages/pokemon-emerald/versions

# Get specific version (includes external URLs and checksums)
curl https://api.example.com/v1/island/packages/pokemon-emerald/2.1.0
```

Response includes external URLs for direct download:

```json
{
  "name": "pokemon-emerald",
  "version": "2.1.0",
  "distributions": [
    {
      "filename": "pokemon_emerald-2.1.0-py3-none-any.island",
      "external_url": "https://github.com/user/repo/releases/download/v2.1.0/pokemon_emerald-2.1.0-py3-none-any.island",
      "sha256": "a1b2c3d4e5f6...",
      "size": 123456,
      "platform_tag": "py3-none-any",
      "url_status": "active"
    }
  ]
}
```

#### Register Packages (Authenticated)

```bash
# Register with external URL and checksum
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-game",
    "version": "1.0.0",
    "game": "My Game",
    "description": "My awesome game",
    "authors": ["Your Name"],
    "minimum_ap_version": "0.5.0",
    "entry_points": {"my_game": "my_game.world:MyGameWorld"},
    "distributions": [{
      "filename": "my_game-1.0.0-py3-none-any.island",
      "url": "https://github.com/user/repo/releases/download/v1.0.0/my_game-1.0.0-py3-none-any.island",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "size": 12345,
      "platform_tag": "py3-none-any"
    }]
  }' \
  "https://api.example.com/v1/island/register"
```

#### Get Full Index (Offline Tooling)

```bash
# Download complete package index (includes external URLs and checksums)
curl https://api.example.com/v1/island/index.json
```

## GitHub Actions Workflow

The recommended way to publish island packages is through GitHub Actions:

```yaml
# .github/workflows/release.yml
name: Release

on:
  release:
    types: [published]

permissions:
  contents: write
  id-token: write

jobs:
  build-and-register:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install island-cli
        run: pip install island-cli
      
      - name: Build distributions
        run: island build
      
      - name: Upload release assets
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          for file in dist/*.island dist/*.tar.gz; do
            if [ -f "$file" ]; then
              gh release upload ${{ github.event.release.tag_name }} "$file" --clobber
            fi
          done
      
      - name: Register with repository
        env:
          ISLAND_TOKEN: ${{ secrets.ISLAND_TOKEN }}
        run: |
          RELEASE_URL="https://github.com/${{ github.repository }}/releases/download/${{ github.event.release.tag_name }}"
          
          ARGS=""
          for file in dist/*.island dist/*.tar.gz; do
            if [ -f "$file" ]; then
              filename=$(basename "$file")
              ARGS="$ARGS --url ${RELEASE_URL}/${filename} --file ${file}"
            fi
          done
          
          island register $ARGS
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and workflow instructions.

## Architecture

```
island-cli ──► island-build ──► island-vendor ──► island-manifest ──► island-version
                    │                                     │
                    └─────────────────────────────────────┘
                     
island-api ──► island-manifest ──► island-version
```

### Package Dependencies

- **island-version**: No dependencies (stdlib only)
- **island-manifest**: Depends on island-version, jsonschema, tomli
- **island-vendor**: Depends on island-manifest
- **island-build**: Depends on island-manifest, island-version, island-vendor
- **island-api**: Depends on island-manifest, island-version, FastAPI, SQLAlchemy
- **island-cli**: Depends on island-build, Click, httpx

## API Documentation

The API server provides OpenAPI documentation at:
- **Swagger UI**: `http://localhost:8000/docs`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

See [packages/island-api/](packages/island-api/) for detailed API documentation.

## License

MIT License
