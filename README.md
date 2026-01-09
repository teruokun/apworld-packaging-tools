# archipelago-repository

APWorld packaging and repository tools for the Archipelago multiworld randomizer ecosystem.

**Note: Currently, all of the code in this repository is generated using AI. While the workflow is a multi-phase process designed to ensure quality, please review carefully.**

## Overview

This monorepo provides a complete toolchain for building, validating, and distributing APWorld packages:

- **Build Tools**: Create `.apworld` binary distributions and `.tar.gz` source distributions
- **Package Index API**: Host and serve APWorld packages with search, versioning, and authentication
- **CLI**: Developer-friendly commands for the full package lifecycle

## Packages

| Package | Description | Install |
|---------|-------------|---------|
| [apworld-version](packages/apworld-version/) | Semantic version parsing and comparison | `pip install apworld-version` |
| [apworld-manifest](packages/apworld-manifest/) | Manifest schema, validation, transformation | `pip install apworld-manifest` |
| [apworld-vendor](packages/apworld-vendor/) | Dependency vendoring and import rewriting | `pip install apworld-vendor` |
| [apworld-build](packages/apworld-build/) | Distribution building (.apworld, .tar.gz) | `pip install apworld-build` |
| [apworld-api](packages/apworld-api/) | Repository server (FastAPI) | `pip install apworld-api` |
| [apworld-cli](packages/apworld-cli/) | CLI tool for developers | `pip install apworld-cli` |

## Quick Start

### For World Developers

Install the CLI tool to build and publish your APWorld:

```console
pip install apworld-cli
```

#### Initialize a New Project

```console
apworld init my-game
cd my-game
```

This creates a project structure with:
- `pyproject.toml` - Project configuration with `[tool.apworld]` section
- `src/my_game/` - Source code directory
- `tests/` - Test directory

#### Configure Your APWorld

Edit `pyproject.toml` to configure your APWorld:

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

[tool.apworld]
game = "My Game"
minimum_ap_version = "0.5.0"
maximum_ap_version = "0.6.99"

[tool.apworld.vendor]
exclude = ["typing_extensions"]
```

#### Build Your APWorld

```console
# Build both source and binary distributions
apworld build

# Build only the .apworld binary
apworld build --apworld

# Build only the source distribution
apworld build --sdist
```

Output files are placed in `dist/`:
- `my_game-1.0.0-py3-none-any.apworld` - Binary distribution
- `my_game-1.0.0.tar.gz` - Source distribution

#### Validate Your Package

```console
apworld validate
```

This checks:
- Manifest schema compliance
- Version format (semantic versioning)
- Package structure
- Required files

#### Publish to Repository

```console
# Publish using API token
apworld publish --token YOUR_API_TOKEN

# Publish to a custom repository
apworld publish --repository https://custom.repo.example.com
```

#### Migrate Legacy Projects

If you have an existing APWorld with only `archipelago.json`:

```console
# Migrate to modern schema
apworld migrate

# Also generate pyproject.toml
apworld migrate --generate-pyproject
```

### For Repository Operators

Install and run the API server:

```console
pip install apworld-api
```

#### Basic Setup

```console
# Run with default SQLite database
uvicorn apworld_api:app --host 0.0.0.0 --port 8000
```

#### Production Configuration

Configure via environment variables:

```bash
# Database
export APWORLD_DATABASE_URL="postgresql://user:pass@localhost/apworld"

# Storage backend
export APWORLD_STORAGE_BACKEND="s3"
export APWORLD_STORAGE_S3_BUCKET="my-apworld-packages"

# Rate limiting
export APWORLD_RATE_LIMIT_ENABLED="true"
export APWORLD_RATE_LIMIT_RPM="100"

# OIDC for Trusted Publishers
export APWORLD_OIDC_ENABLED="true"
export APWORLD_OIDC_ISSUER="https://token.actions.githubusercontent.com"

uvicorn apworld_api:app --host 0.0.0.0 --port 8000
```

#### Using Docker

```dockerfile
FROM python:3.11-slim
RUN pip install apworld-api uvicorn
EXPOSE 8000
CMD ["uvicorn", "apworld_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### API Usage Examples

#### Search Packages

```bash
# List all packages
curl https://api.example.com/v1/packages

# Search by keyword
curl "https://api.example.com/v1/search?q=pokemon"

# Filter by game
curl "https://api.example.com/v1/search?game=Pokemon%20Emerald"

# Filter by Core AP compatibility
curl "https://api.example.com/v1/search?compatible_with=0.5.0"
```

#### Get Package Information

```bash
# Get package metadata
curl https://api.example.com/v1/packages/pokemon-emerald

# List all versions
curl https://api.example.com/v1/packages/pokemon-emerald/versions

# Get specific version
curl https://api.example.com/v1/packages/pokemon-emerald/2.1.0
```

#### Download Packages

```bash
# Download a distribution
curl -O https://api.example.com/v1/packages/pokemon-emerald/2.1.0/download/pokemon_emerald-2.1.0-py3-none-any.apworld

# Verify checksum (from X-Checksum-SHA256 header)
sha256sum pokemon_emerald-2.1.0-py3-none-any.apworld
```

#### Upload Packages (Authenticated)

```bash
# Upload with API token
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@dist/my_game-1.0.0-py3-none-any.apworld" \
  "https://api.example.com/v1/packages/my-game/upload"
```

#### Get Full Index (Offline Tooling)

```bash
# Download complete package index
curl https://api.example.com/v1/index.json
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and workflow instructions.

## Architecture

```
apworld-cli ──► apworld-build ──► apworld-vendor ──► apworld-manifest ──► apworld-version
                     │                                      │
                     └──────────────────────────────────────┘
                     
apworld-api ──► apworld-manifest ──► apworld-version
```

### Package Dependencies

- **apworld-version**: No dependencies (stdlib only)
- **apworld-manifest**: Depends on apworld-version, jsonschema, tomli
- **apworld-vendor**: Depends on apworld-manifest
- **apworld-build**: Depends on apworld-manifest, apworld-version, apworld-vendor
- **apworld-api**: Depends on apworld-manifest, apworld-version, FastAPI, SQLAlchemy
- **apworld-cli**: Depends on apworld-build, Click, httpx

## API Documentation

The API server provides OpenAPI documentation at:
- **Swagger UI**: `http://localhost:8000/docs`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

See [packages/apworld-api/](packages/apworld-api/) for detailed API documentation.

## License

MIT License
