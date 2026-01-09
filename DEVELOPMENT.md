# Development Guide

This project uses [Hatch](https://hatch.pypa.io/) for environment management, testing, and development workflows.

## Prerequisites

Install Hatch using one of these methods:

```bash
# Using pip
pip install hatch

# Using pipx (recommended for CLI tools)
pipx install hatch

# Using uvx (if you have uv installed)
uvx hatch
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/ArchipelagoMW/archipelago-repository
cd archipelago-repository

# Run all tests
hatch test

# Run tests for a specific Python version
hatch test -py 3.12
```

## Development Workflow

### Running Tests

```bash
# Run tests across all Python versions (3.11, 3.12, 3.13)
hatch test

# Run tests for a specific Python version
hatch test -py 3.11
hatch test -py 3.12
hatch test -py 3.13

# Run tests with coverage
hatch test --cover

# Run tests in the default environment (current Python)
hatch run test
```

### Code Quality

```bash
# Lint code
hatch run lint:check

# Format code
hatch run lint:format

# Fix linting issues automatically
hatch run lint:fix

# Type checking
hatch run types:check
```

### Working with Packages

This is a monorepo with multiple packages in `packages/`. Each package can be installed in editable mode:

```bash
# Enter the default Hatch environment shell
hatch shell

# All packages are available for import
python -c "import apworld_version; print(apworld_version.__version__)"
```

### Environment Management

```bash
# Show all environments
hatch env show

# Create/enter the default environment
hatch shell

# Run a command in an environment
hatch run <command>

# Remove all environments (clean slate)
hatch env prune
```

## Project Structure

```
archipelago-repository/
├── packages/                    # Individual packages
│   ├── apworld-version/        # Semantic versioning
│   ├── apworld-manifest/       # Manifest handling
│   ├── apworld-vendor/         # Dependency vendoring
│   ├── apworld-build/          # Build tools
│   ├── apworld-api/            # Repository API server
│   └── apworld-cli/            # CLI tool
├── tests/                       # Integration tests
├── pyproject.toml              # Hatch configuration
└── DEVELOPMENT.md              # This file
```

## CI/CD

The GitHub Actions workflow uses Hatch for testing across multiple Python versions and platforms. See `.github/workflows/ci.yml` for details.

## Troubleshooting

### Tests failing with import errors

Ensure you're running tests through Hatch which sets up the environment correctly:

```bash
hatch test
```

### Environment issues

Reset your environments:

```bash
hatch env prune
hatch test
```
