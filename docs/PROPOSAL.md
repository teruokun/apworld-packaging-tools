# APWorld Repository: A Modern Packaging Ecosystem

## Vision

The Archipelago Repository project reimagines how APWorld packages are built, distributed, and consumed. The goal is to create a seamless experience for everyone in the ecosystem—from developers crafting new game integrations to players assembling their multiworld sessions.

---

## Core Tenets

### 1. Seamless Developer Experience

APWorld development should feel natural to anyone familiar with modern Python packaging. Developers shouldn't need to learn bespoke tooling or fight against the system to get their work published.

- **Familiar workflows**: `pyproject.toml` configuration, standard build commands, conventional project layouts
- **Instant feedback**: Validation catches issues before they reach users
- **Zero-friction publishing**: GitHub releases trigger automatic repository updates

### 2. Seamless Player & Organizer Experience

Players and tournament organizers need reliable, discoverable packages that "just work."

- **Searchable registry**: Find APWorlds by game name, author, tags, or compatibility
- **Guaranteed compatibility**: Clear version bounds prevent broken installations
- **Offline-friendly**: Full index available for air-gapped setups and custom tooling

---

## Distribution Strategy

### The Problem with Current APWorlds

The existing `.apworld` format has served the community well, but it carries limitations:

| Issue | Impact |
|-------|--------|
| No declared dependencies | Users manually install requirements |
| Opaque binary blobs | Can't inspect or audit without extraction |
| No integrity verification | No checksums, no signatures |
| Tight version coupling | APWorlds built for 0.6.0 fail on 0.6.1 |

### Our Solution: Dual Distribution Formats

We introduce two complementary distribution formats:

#### Binary Distribution (`.apworld`)

The familiar format, extended with designs from Python binary wheels and enhanced with:

- **Vendored dependencies**: All third-party code bundled and import-rewritten to prevent conflicts and keep behaviors consistent
- **Deterministic builds**: Same source always produces identical output
- **Embedded metadata**: Rich manifest with checksums, compatibility bounds, and provenance

```
my_game-1.0.0-py3-none-any.apworld
├── worlds/my_game/
│   ├── __init__.py
│   ├── archipelago.json      # Enhanced manifest
│   ├── _vendor/              # Vendored dependencies
│   └── ...
└── METADATA                  # PEP 566 metadata
```

#### Source Distribution (`.tar.gz`)

A new format for transparency and reproducibility:

- **Auditable**: Full source code, no compiled artifacts
- **Rebuildable**: Anyone can verify the binary matches the source
- **Development-friendly**: Install in editable mode for local development
- **Closes platform gaps**: Anyone with a non-standard platform without a binary apworld can build it from source locally, just like `pip` does with source distributions and binary wheels

```
my_game-1.0.0.tar.gz
├── pyproject.toml
├── src/my_game/
│   ├── __init__.py
│   └── world.py
├── tests/
└── LICENSE
```

### Batteries-Included Philosophy

APWorlds should be self-contained. When you download an APWorld, it should work—no hunting for dependencies, no version conflicts with other worlds.

**Dependency Vendoring**:
- Third-party packages are copied into `_vendor/`
- Import statements are rewritten: `import requests` → `from ._vendor import requests`
- Isolation prevents conflicts between worlds using different library versions

**Exclusion Controls**:
- Standard library extensions (like `typing_extensions`) can be excluded
- Archipelago-provided packages are never vendored
- Developers control what gets bundled via `[tool.apworld.vendor]`

### Sandboxing Strategy

APWorlds execute within the Archipelago runtime, which creates security considerations. Our approach:

1. **Static Analysis**: Scan for dangerous patterns during upload (filesystem access, network calls, code execution)
2. **Capability Declaration**: APWorlds declare what system access they need
3. **Runtime Boundaries**: Future Archipelago versions can enforce declared capabilities

This isn't about distrust—it's about enabling a healthy ecosystem where users can confidently install community packages.

---

## Developer Workflow

### Getting Started

```bash
# Install the CLI
pip install apworld-cli

# Create a new project
apworld init my-game
cd my-game
```

The generated project includes:
- Modern `pyproject.toml` with `[tool.apworld]` configuration
- Comprehensive docstrings and example code
- GitHub Actions for CI/CD and publishing
- Test scaffolding with pytest

### Development Cycle

```bash
# Validate your package
apworld validate

# Build distributions
apworld build

# Run tests
pytest
```

### Publishing

Two paths to publication:

**Manual Upload**:
```bash
apworld publish --token YOUR_API_TOKEN
```

**Automated via GitHub Actions** (recommended):
1. Configure trusted publishing on the repository
2. Create a GitHub release
3. The workflow builds, validates, and publishes automatically

---

## Repository Features

### Rich Metadata & Search

The repository indexes extensive metadata for discovery:

- **Game information**: Name, description, authors, homepage
- **Compatibility**: Minimum/maximum Archipelago versions
- **Classification**: Tags, categories, maturity level
- **Statistics**: Download counts, update frequency

**Search Examples**:
```bash
# Find Pokemon-related APWorlds
curl "https://api.example.com/v1/search?q=pokemon"

# Find APWorlds compatible with AP 0.5.x
curl "https://api.example.com/v1/search?compatible_with=0.5.0"

# Find recently updated APWorlds
curl "https://api.example.com/v1/search?sort=updated&order=desc"
```

### Quality Signals (Future)

We envision additional automated checks that provide quality signals to users:

| Check | Purpose |
|-------|---------|
| **Test Coverage** | Does the APWorld have tests? Do they pass? |
| **Performance Scan** | Generation time benchmarks, memory usage |
| **Compatibility Matrix** | Tested against which AP versions? |
| **Security Audit** | Static analysis for concerning patterns |
| **Documentation Score** | Are options documented? Setup guide present? |

These signals help users make informed decisions without gatekeeping—packages aren't rejected, but users see what's been verified.

### Offline Index

The complete package index is available as a single JSON file:

```bash
curl https://api.example.com/v1/index.json
```

This enables:
- Offline package managers
- Custom tooling and integrations
- Mirror sites and CDN distribution
- Tournament setups without internet dependency

---

## Authentication & Ownership

### GitHub Trusted Publishing

We adopt PyPI's trusted publishing model, eliminating the need for long-lived API tokens.

**How It Works**:

1. Developer registers their APWorld on the repository
2. Developer configures their GitHub repository as a trusted publisher
3. GitHub Actions workflow requests a short-lived OIDC token
4. Repository verifies the token came from the authorized repository
5. Package is published without any stored secrets

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

Every published package includes provenance information:

```json
{
  "publisher": "github:ArchipelagoMW/apworld-pokemon-emerald",
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
# Migrate legacy archipelago.json to modern format
apworld migrate

# Generate pyproject.toml from existing manifest
apworld migrate --generate-pyproject
```

The migration tool:
- Preserves all existing metadata
- Adds recommended fields with sensible defaults
- Validates the result

### For Archipelago Core

The repository is designed to complement, not replace, existing infrastructure:

- APWorlds remain compatible with current loading mechanisms
- The enhanced manifest is backward-compatible
- Adoption is opt-in for developers

---

## Summary

The APWorld Repository project delivers:

1. **Modern tooling** that respects developers' time and expertise
2. **Reliable packages** that work out of the box for players
3. **Transparent distribution** with auditable source and reproducible builds
4. **Secure publishing** through GitHub's trusted infrastructure
5. **Rich discovery** to help users find the APWorlds they want

We're building the packaging ecosystem the Archipelago community deserves—one that scales with the project's growth while remaining accessible to newcomers.
