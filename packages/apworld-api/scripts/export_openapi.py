#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export OpenAPI specification from the APWorld API.

This script generates the OpenAPI 3.0+ specification from the FastAPI application
and writes it to a JSON file.

Usage:
    python scripts/export_openapi.py [output_path]

Examples:
    python scripts/export_openapi.py                    # Writes to openapi.json
    python scripts/export_openapi.py docs/openapi.json  # Custom output path
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def export_openapi(output_path: str | Path = "openapi.json") -> None:
    """Export the OpenAPI specification to a JSON file.

    Args:
        output_path: Path to write the OpenAPI spec (default: openapi.json)
    """
    from apworld_api import create_app

    # Create the app to generate the OpenAPI schema
    app = create_app()

    # Get the OpenAPI schema
    openapi_schema = app.openapi()

    # Write to file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"OpenAPI specification exported to: {output_path}")
    print(f"  Title: {openapi_schema.get('info', {}).get('title')}")
    print(f"  Version: {openapi_schema.get('info', {}).get('version')}")
    print(f"  Paths: {len(openapi_schema.get('paths', {}))}")


def main() -> None:
    """Main entry point."""
    output_path = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    export_openapi(output_path)


if __name__ == "__main__":
    main()
