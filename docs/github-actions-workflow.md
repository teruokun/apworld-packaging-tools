# GitHub Actions Workflow for Island Package Registration

This document provides a complete GitHub Actions workflow template for automatically building and registering island packages when you create a GitHub Release.

## Overview

The workflow:
1. Triggers when you publish a GitHub Release
2. Builds your island package (`.island` and `.tar.gz`)
3. Uploads the built assets to the GitHub Release
4. Registers the package with the Island Registry

## Prerequisites

1. **Island CLI installed**: The workflow uses `island-cli` for building and registration
2. **API Token**: Store your registry API token as a GitHub secret named `ISLAND_TOKEN`
3. **Valid `pyproject.toml`**: Your project must have proper island configuration

## Complete Workflow Template

Create `.github/workflows/release.yml` in your repository:

```yaml
name: Release Island Package

on:
  release:
    types: [published]

permissions:
  contents: write      # Required for uploading release assets
  id-token: write      # Required for OIDC authentication (optional)

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
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install island-cli
      
      - name: Validate package
        run: island validate
      
      - name: Build distributions
        run: island build
      
      - name: List built files
        run: ls -la dist/
      
      - name: Upload release assets
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          for file in dist/*.island dist/*.tar.gz; do
            if [ -f "$file" ]; then
              echo "Uploading $file..."
              gh release upload ${{ github.event.release.tag_name }} "$file" --clobber
            fi
          done
      
      - name: Register with Island Registry
        env:
          ISLAND_TOKEN: ${{ secrets.ISLAND_TOKEN }}
        run: |
          RELEASE_URL="https://github.com/${{ github.repository }}/releases/download/${{ github.event.release.tag_name }}"
          
          # Build registration arguments
          ARGS=""
          for file in dist/*.island dist/*.tar.gz; do
            if [ -f "$file" ]; then
              filename=$(basename "$file")
              echo "Adding distribution: $filename"
              ARGS="$ARGS --url ${RELEASE_URL}/${filename} --file ${file}"
            fi
          done
          
          echo "Registering package..."
          island register $ARGS
```

## Setting Up the API Token

1. **Get your API token** from the Island Registry
2. **Add it as a GitHub secret**:
   - Go to your repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `ISLAND_TOKEN`
   - Value: Your API token

## OIDC Authentication (Advanced)

For enhanced security, you can use GitHub OIDC tokens instead of stored secrets. This eliminates the need to manage long-lived API tokens.

### How OIDC Works

1. GitHub Actions generates a short-lived OIDC token
2. The token includes claims about the repository and workflow
3. The registry verifies the token and authorizes the registration
4. No secrets are stored in your repository

### Setting Up OIDC

1. **Configure trusted publisher** in the Island Registry:
   - Register your package (first time only)
   - Add your GitHub repository as a trusted publisher
   - Specify the workflow file path (e.g., `.github/workflows/release.yml`)

2. **Update your workflow** to request an OIDC token:

```yaml
name: Release Island Package (OIDC)

on:
  release:
    types: [published]

permissions:
  contents: write
  id-token: write  # Required for OIDC

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
      
      - name: Install dependencies
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
      
      - name: Get OIDC token
        id: oidc
        uses: actions/github-script@v7
        with:
          script: |
            const token = await core.getIDToken('island-registry');
            core.setOutput('token', token);
      
      - name: Register with Island Registry
        env:
          ISLAND_TOKEN: ${{ steps.oidc.outputs.token }}
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

### OIDC Benefits

- **No stored secrets**: Tokens are generated on-demand
- **Short-lived**: Tokens expire quickly, reducing risk
- **Auditable**: Every registration tied to specific workflow run
- **Revocable**: Remove trusted publisher to instantly revoke access

## Workflow Variations

### Build Only (No Registration)

For testing builds without registering:

```yaml
name: Build Island Package

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install island-cli
      - run: island validate
      - run: island build
      - uses: actions/upload-artifact@v4
        with:
          name: distributions
          path: dist/
```

### Multi-Platform Builds

For packages with platform-specific code:

```yaml
name: Release Multi-Platform

on:
  release:
    types: [published]

permissions:
  contents: write
  id-token: write

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.11"]
    
    runs-on: ${{ matrix.os }}
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install island-cli
      - run: island build
      - uses: actions/upload-artifact@v4
        with:
          name: dist-${{ matrix.os }}
          path: dist/
  
  register:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          path: dist/
          merge-multiple: true
      
      - name: Upload all assets
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          for file in dist/*.island dist/*.tar.gz; do
            if [ -f "$file" ]; then
              gh release upload ${{ github.event.release.tag_name }} "$file" --clobber
            fi
          done
      
      - name: Register all distributions
        env:
          ISLAND_TOKEN: ${{ secrets.ISLAND_TOKEN }}
        run: |
          pip install island-cli
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

## Troubleshooting

### Registration Fails with 400 Error

The registry validates URLs and checksums before accepting registration:

- **URL not accessible**: Ensure the release assets are public
- **Checksum mismatch**: The file at the URL doesn't match the local file
- **Invalid checksum format**: Must be 64 lowercase hex characters

### Registration Fails with 401 Error

Authentication failed:

- Check that `ISLAND_TOKEN` secret is set correctly
- Verify the token hasn't expired
- For OIDC, ensure trusted publisher is configured

### Registration Fails with 403 Error

Authorization failed:

- You may not own this package
- For first-time registration, the package name may be taken
- For OIDC, verify the repository is configured as trusted publisher

### Assets Not Uploading

- Ensure `GITHUB_TOKEN` has `contents: write` permission
- Check that the release exists and tag is correct
- Verify files exist in `dist/` directory

## Best Practices

1. **Always validate first**: Run `island validate` before building
2. **Use semantic versioning**: Tag releases with `v1.0.0` format
3. **Test locally**: Run `island build` and `island register --dry-run` locally first
4. **Keep tokens secure**: Never commit tokens to your repository
5. **Use OIDC when possible**: More secure than stored secrets
6. **Pin action versions**: Use specific versions like `@v4` instead of `@latest`
