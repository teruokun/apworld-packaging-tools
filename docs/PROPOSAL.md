# Island Repository: A Go-Style Package Registry

## Vision

The Archipelago Repository project reimagines how game world packages are built, discovered, and consumed. The goal is to create a seamless experience for everyone in the ecosystem—from developers crafting new game integrations to players assembling their multiworld sessions.

The **island format** (`.island`) is our modern packaging standard, designed as a Python wheel extension specifically for Archipelago game worlds. It provides clear differentiation from the legacy APWorld format used by Archipelago core, with stronger guarantees around packaging, dependency management, and entry points.

The repository operates as a **registry** rather than a package host—similar to Go's module proxy model. Package binaries are hosted externally (e.g., GitHub Releases), while the registry indexes metadata, URLs, and checksums. Clients download directly from external sources and verify integrity locally.

---

## Core Tenets

### 1. Registry-Only Model

The repository serves as a searchable index of known island packages, not a vendor of the packages themselves:

- **Metadata storage**: Package names, versions, descriptions, entry points, compatibility bounds
- **External URLs**: Links to assets hosted on GitHub Releases or other services
- **Checksums**: SHA256 hashes for integrity verification
- **No binary hosting**: The registry never stores or serves actual package files

This model is similar to how Go modules work with `go.sum` verification—the registry provides discovery and integrity guarantees, while actual downloads happen from the source.

### 2. Seamless Developer Experience

Island development should feel natural to anyone familiar with modern Python packaging. Developers shouldn't need to learn bespoke tooling or fight against the system to get their work published.

- **Familiar workflows**: `pyproject.toml` configuration, standard build commands, conventional project layouts
- **Instant feedback**: Validation catches issues before they reach users
- **Zero-friction publishing**: GitHub releases trigger automatic registry updates

### 3. Seamless Player & Organizer Experience

Players and tournament organizers need reliable, discoverable packages that "just work."

- **Searchable registry**: Find island packages by game name, author, tags, entry points, or compatibility
- **Guaranteed compatibility**: Clear version bounds prevent broken installations
- **Client-side verification**: Downloads are verified against registry-provided checksums
- **Offline-friendly**: Full index available for air-gapped setups and custom tooling

---

## Distribution Strategy

### The Problem with Legacy APWorld Format

The existing `.apworld` format used by Archipelago core has served the community well, but it carries limitations:

| Issue | Impact |
|-------|--------|
| Dependencies are in a shared namespace | Archipelago must install dependencies and handle conflict resolution |
| Opaque binary blobs | Can't inspect or audit without extraction |
| No integrity verification | No checksums, no signatures |
| Tight version coupling | APWorlds built for 0.6.0 fail on 0.6.1 |
| No entry point declarations | Can't index or discover WebWorld implementations, relies on scanning/implicit load path |
| No platform tags | Builds containing precompiled binaries can't represent their OS/Arch compatibility or if they need to be rebuilt locally |

### Our Solution: The Island Format

The island format (`.island`) is a Python wheel extension that addresses these limitations:

#### Key Differences from Legacy APWorld

| Feature | Legacy APWorld | Island Format |
|---------|----------------|---------------|
| File extension | `.apworld` | `.island` |
| Entry points | Not required | **Required** (`ap-island`) |
| Platform tags | Not supported | Full PEP 425 support |
| Wheel metadata | Partial | Full PEP 427 compliance |
| Dependency vendoring | Optional | **Required** |
| Configuration | `archipelago.json` | `pyproject.toml` with `[tool.island]` |
| AP core compatible | Yes | **No** (separate ecosystem) |

> **Important**: Island packages are NOT compatible with Archipelago core's APWorld loading mechanism. The island format is designed for the repository ecosystem, providing enhanced features at the cost of direct AP core compatibility.

### Dual Distribution Formats

We provide two complementary distribution formats:

#### Binary Distribution (`.island`)

A Python wheel extension with:

- **Mandatory entry points**: All island packages must declare `ap-island` entry points
- **Platform tags**: Full support for Python version, ABI, and platform tags
- **Vendored dependencies**: All third-party code bundled and import-rewritten
- **Deterministic builds**: Same source always produces identical output
- **Embedded metadata**: Rich manifest with checksums, compatibility bounds, and provenance

```
my_game-1.0.0-py3-none-any.island
├── my_game/
│   ├── __init__.py
│   ├── world.py              # WebWorld implementation
│   ├── _vendor/              # Vendored dependencies
│   └── ...
├── my_game-1.0.0.dist-info/
│   ├── WHEEL                 # PEP 427 wheel metadata
│   ├── METADATA              # PEP 566 package metadata
│   ├── RECORD                # File manifest with checksums
│   ├── entry_points.txt      # Entry point declarations
│   └── island.json           # Island-specific metadata
└── [optional platform-specific files]
```

#### Source Distribution (`.tar.gz`)

A standard format for transparency and reproducibility:

- **Auditable**: Full source code, no compiled artifacts
- **Rebuildable**: Anyone can verify the binary matches the source
- **Development-friendly**: Install in editable mode for local development
- **Closes platform gaps**: Build from source for non-standard platforms

```
my_game-1.0.0.tar.gz
├── pyproject.toml
├── src/my_game/
│   ├── __init__.py
│   └── world.py
├── tests/
└── LICENSE
```

### Filename Format

Island packages follow Python wheel naming conventions:

```
{distribution}-{version}(-{build})?-{python}-{abi}-{platform}.island
```

Examples:
- `pokemon_emerald-2.1.0-py3-none-any.island` (pure Python, any platform)
- `my_game-1.0.0-cp311-cp311-macosx_11_0_arm64.island` (platform-specific)
- `complex_world-3.0.0-1-py3-none-linux_x86_64.island` (with build tag)

### Batteries-Included Philosophy

Island packages should be self-contained. When you download an island package, it should work—no hunting for dependencies, no version conflicts with other worlds.

**Dependency Vendoring**:
- Third-party packages are copied into `_vendor/`
- Import statements are rewritten: `import requests` → `from ._vendor import requests`
- Isolation prevents conflicts between worlds using different library versions

**Exclusion Controls**:
- Standard library extensions (like `typing_extensions`) can be excluded
- Archipelago-provided packages are never vendored
- Developers control what gets bundled via `[tool.island.vendor]`

### Entry Point Requirements

All island packages must declare at least one `ap-island` entry point:

```toml
[project.entry-points.ap-island]
my_game = "my_game.world:MyGameWorld"
```

Entry points enable:
- **Registry indexing**: Discover WebWorld implementations automatically
- **Search by game**: Find all packages for a specific game
- **Multiple worlds**: One package can provide multiple WebWorld implementations

### Sandboxing Strategy

Island packages execute within the Archipelago runtime, which creates security considerations. Our approach:

1. **Static Analysis**: Scan for dangerous patterns during registration (filesystem access, network calls, code execution)
2. **Capability Declaration**: Island packages declare what system access they need
3. **Runtime Boundaries**: Future Archipelago versions can enforce declared capabilities

This isn't about distrust—it's about enabling a healthy ecosystem where users can confidently install community packages.

---

## Registration Workflow

### How Registration Works

Unlike traditional package repositories that host binaries, the Island Registry uses a registration model:

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Developer  │────▶│  GitHub Release │────▶│   Registry   │
│             │     │  (hosts files)  │     │ (stores URLs │
│             │     │                 │     │  + metadata) │
└─────────────┘     └─────────────────┘     └──────────────┘
                            │                      │
                            │                      │
                            ▼                      ▼
                    ┌─────────────┐        ┌─────────────┐
                    │   Client    │◀───────│  Metadata   │
                    │ (downloads  │        │  + URLs +   │
                    │  + verifies)│        │  Checksums  │
                    └─────────────┘        └─────────────┘
```

1. **Developer builds** the island package locally
2. **Developer uploads** assets to GitHub Release (or other hosting)
3. **Developer registers** with the registry, providing URLs and checksums
4. **Registry verifies** URLs are accessible and checksums match
5. **Client queries** the registry for package metadata
6. **Client downloads** directly from external URL
7. **Client verifies** checksum matches registry-provided value

### Registration API

Register a package version by providing metadata and external URLs:

```bash
# Using the CLI
island register \
    --url https://github.com/user/repo/releases/download/v1.0.0/my_game-1.0.0-py3-none-any.island \
    --file dist/my_game-1.0.0-py3-none-any.island

# The CLI computes the checksum from the local file and submits:
# - Package metadata (from pyproject.toml)
# - External URL
# - SHA256 checksum
# - File size
```

The registry validates before accepting:
- URL is accessible (HTTP HEAD returns 2xx)
- URL uses HTTPS
- Downloaded content matches provided checksum
- Downloaded size matches provided size

### Client-Side Verification

When installing packages, the client:

1. **Queries the registry** for package metadata (including external URL and checksum)
2. **Downloads from external URL** (e.g., GitHub Releases)
3. **Computes SHA256** of downloaded content
4. **Verifies checksum** matches registry-provided value
5. **Rejects on mismatch** with clear error message

```bash
# Install a package (downloads from external URL, verifies checksum)
island install my-game

# Output:
# Fetching package info for my-game...
# Package: my-game v1.0.0
# File: my_game-1.0.0-py3-none-any.island
# Downloading from: https://github.com/user/repo/releases/download/v1.0.0/...
# Successfully installed my-game v1.0.0
# Checksum verified: a1b2c3d4e5f6...
```

### Checksum Format

- **Algorithm**: SHA256
- **Format**: 64-character lowercase hexadecimal string
- **Example**: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

---

## Developer Workflow

### Getting Started

```bash
# Install the CLI
pip install island-cli

# Create a new project
island init my-game
cd my-game
```

The generated project includes:
- Modern `pyproject.toml` with `[tool.island]` configuration
- Required `ap-island` entry points
- Comprehensive docstrings and example code
- GitHub Actions for CI/CD and registration
- Test scaffolding with pytest

### Development Cycle

```bash
# Validate your package
island validate

# Build distributions
island build

# Run tests
pytest
```

### Publishing via GitHub Actions (Recommended)

The recommended workflow uses GitHub Releases to trigger automatic registration:

1. **Create a GitHub Release** with a version tag (e.g., `v1.0.0`)
2. **GitHub Actions workflow** builds the package
3. **Workflow uploads** assets to the release
4. **Workflow registers** with the registry using OIDC authentication

See the [GitHub Actions Workflow](#github-actions-workflow) section for the complete workflow template.

### Manual Registration

For manual registration from the command line:

```bash
# Build your package
island build

# Upload to GitHub Release manually, then register
island register \
    --url https://github.com/user/repo/releases/download/v1.0.0/my_game-1.0.0-py3-none-any.island \
    --file dist/my_game-1.0.0-py3-none-any.island \
    --token YOUR_API_TOKEN
```

---

## GitHub Actions Workflow

The recommended way to publish island packages is through GitHub Actions triggered by releases. This provides:

- **Automated builds**: Consistent, reproducible builds
- **OIDC authentication**: No stored secrets required
- **Audit trail**: Every release tied to a specific commit

### Complete Workflow Template

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  release:
    types: [published]

permissions:
  contents: write      # For uploading release assets
  id-token: write      # For OIDC authentication with registry

jobs:
  build-and-register:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
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
          
          # Build registration arguments
          ARGS=""
          for file in dist/*.island dist/*.tar.gz; do
            if [ -f "$file" ]; then
              filename=$(basename "$file")
              ARGS="$ARGS --url ${RELEASE_URL}/${filename} --file ${file}"
            fi
          done
          
          island register $ARGS
```

### OIDC Authentication Setup

For enhanced security, configure trusted publishing with GitHub OIDC:

1. **Register your package** in the registry (first-time setup)
2. **Configure trusted publisher** linking your GitHub repository
3. **Update workflow** to use OIDC token instead of stored secret

The registry verifies:
- Token came from GitHub Actions
- Token is for the authorized repository
- Workflow matches the configured pattern

Benefits:
- No long-lived secrets to manage or rotate
- Publishing tied to specific repositories
- Instant revocation by removing trusted publisher

---

## Repository Features

### Rich Metadata & Search

The registry indexes extensive metadata for discovery:

- **Game information**: Name, description, authors, homepage
- **Entry points**: All `ap-island` entry points for WebWorld discovery
- **Compatibility**: Minimum/maximum Archipelago versions
- **Platform tags**: Available platform variants
- **External URLs**: Links to download locations with checksums
- **Classification**: Tags, categories, maturity level

**Search Examples**:
```bash
# Find Pokemon-related island packages
curl "https://api.example.com/v1/island/search?q=pokemon"

# Find packages compatible with AP 0.5.x
curl "https://api.example.com/v1/island/search?compatible_with=0.5.0"

# Find packages by entry point
curl "https://api.example.com/v1/island/search?entry_point=pokemon_emerald"

# Find packages by game
curl "https://api.example.com/v1/island/search?game=Pokemon%20Emerald"

# Filter by platform
curl "https://api.example.com/v1/island/search?platform=macosx_arm64"
```

### Quality Signals (Future)

We envision additional automated checks that provide quality signals to users:

| Check | Purpose |
|-------|---------|
| **Test Coverage** | Does the island package have tests? Do they pass? |
| **Performance Scan** | Generation time benchmarks, memory usage |
| **Compatibility Matrix** | Tested against which AP versions? |
| **Security Audit** | Static analysis for concerning patterns |
| **Documentation Score** | Are options documented? Setup guide present? |

These signals help users make informed decisions without gatekeeping—packages aren't rejected, but users see what's been verified and can understand what they might be getting into.

### Offline Index

The complete package index is available as a single JSON file:

```bash
curl https://api.example.com/v1/island/index.json
```

This enables:
- Offline package managers
- Custom tooling and integrations
- Mirror sites and CDN distribution
- Tournament setups without internet dependency

The index includes external URLs and checksums for all distributions.

---

## Comparison to Go Modules

The Island Registry model is inspired by Go's module system:

| Aspect | Go Modules | Island Registry |
|--------|------------|-----------------|
| **Index** | `proxy.golang.org` | Island Registry API |
| **Hosting** | Source repos (GitHub, etc.) | GitHub Releases, etc. |
| **Verification** | `go.sum` checksums | SHA256 in registry |
| **Download** | From source or proxy | From external URL |
| **Client verification** | `go mod verify` | `island install` (automatic) |

Key similarities:
- Registry stores metadata and checksums, not binaries
- Clients download from source and verify locally
- Checksums provide integrity guarantees
- Decentralized hosting with centralized discovery

---

## Authentication & Ownership

### GitHub Trusted Publishing

We adopt PyPI's trusted publishing model, eliminating the need for long-lived API tokens.

**How It Works**:

1. Developer registers their island package in the registry
2. Developer configures their GitHub repository as a trusted publisher
3. GitHub Actions workflow requests a short-lived OIDC token
4. Registry verifies the token came from the authorized repository
5. Package is registered without any stored secrets

**Benefits**:
- No API tokens to leak or rotate
- Publishing tied to specific repositories and workflows
- Audit trail of exactly which commit produced each release
- Revocation is instant—just remove the trusted publisher

### Project Ownership Model

Ownership flows from GitHub:

- **Primary Owner**: The GitHub user/org that registered the package
- **Collaborators**: GitHub repository collaborators can publish
- **Transfer**: Ownership transfers follow GitHub repository transfers

This model:
- Leverages existing trust relationships
- Avoids maintaining a separate identity system
- Provides familiar access control patterns
- Enables organization-level package management

### Provenance & Attestation

Every registered package includes provenance information:

```json
{
  "publisher": "github:ArchipelagoMW/island-pokemon-emerald",
  "workflow": ".github/workflows/release.yml",
  "commit": "abc123...",
  "build_time": "2024-01-15T10:30:00Z",
  "attestation": "..."
}
```

Users can verify:
- Which repository produced the package
- Which commit was built
- That the binary matches the source

---

## Migration Path

### For Existing APWorld Developers

```bash
# Migrate legacy APWorld to island format
island migrate --from-apworld

# Generate pyproject.toml from existing manifest
island migrate --generate-pyproject
```

The migration tool:
- Preserves all existing metadata
- Converts `[tool.apworld]` to `[tool.island]`
- Detects WebWorld classes and generates `ap-island` entry points
- Validates the result meets island format requirements

### For Archipelago Core

The island format is designed as a separate ecosystem:

- Island packages are NOT compatible with AP core's APWorld loading
- The enhanced format provides features not available in legacy APWorld
- Developers can maintain both formats if needed for different use cases

---

## Summary

The Island Repository project delivers:

1. **Registry-only model** that indexes packages without hosting binaries
2. **Modern tooling** that respects developers' time and expertise
3. **Reliable packages** with client-side checksum verification
4. **Transparent distribution** with auditable source and reproducible builds
5. **Secure publishing** through GitHub's trusted infrastructure
6. **Rich discovery** with entry point indexing and platform filtering
7. **Clear differentiation** from legacy APWorld format

We're building the packaging ecosystem the Archipelago community deserves—one that scales with the project's growth while remaining accessible to newcomers.
