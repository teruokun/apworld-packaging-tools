# SPDX-License-Identifier: MIT
"""Template engine for directory-based template processing."""

from __future__ import annotations

import re
from pathlib import Path

# Pattern for matching template variables: {{variable_name}}
VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class TemplateError(Exception):
    """Raised when template processing fails."""

    pass


class TemplateEngine:
    """Processes directory-based templates with variable substitution.

    This engine walks a template directory tree, substitutes variables in both
    file/directory names and file contents, and writes the processed files to
    an output directory.

    Variable syntax: {{variable_name}}
    """

    def __init__(self, template_dir: Path) -> None:
        """Initialize with the root template directory.

        Args:
            template_dir: Path to the directory containing template files.

        Raises:
            TemplateError: If the template directory does not exist.
        """
        self.template_dir = template_dir
        if not template_dir.exists():
            raise TemplateError(f"Template directory not found: {template_dir}")

    def _substitute_content(self, content: str, variables: dict[str, str]) -> str:
        """Substitute {{variable}} patterns in file content.

        Args:
            content: The template string containing {{variable}} patterns.
            variables: Dictionary mapping variable names to their values.

        Returns:
            The content with all variables substituted.

        Raises:
            TemplateError: If a variable in the content is not defined.
        """

        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            if var_name not in variables:
                raise TemplateError(f"Undefined template variable: {var_name}")
            return variables[var_name]

        return VARIABLE_PATTERN.sub(replacer, content)

    def _substitute_path(self, path: str, variables: dict[str, str]) -> str:
        """Substitute {{variable}} patterns in a path string.

        Args:
            path: The path string containing {{variable}} patterns.
            variables: Dictionary mapping variable names to their values.

        Returns:
            The path with all variables substituted.

        Raises:
            TemplateError: If a variable in the path is not defined.
        """
        return self._substitute_content(path, variables)

    def _is_binary_file(self, path: Path) -> bool:
        """Check if a file should be treated as binary (no substitution).

        Binary files are detected by checking for null bytes in the first
        chunk of the file.

        Args:
            path: Path to the file to check.

        Returns:
            True if the file appears to be binary, False otherwise.
        """
        try:
            with open(path, "rb") as f:
                chunk = f.read(8192)
                return b"\x00" in chunk
        except OSError:
            return False

    # Allowed hidden directories that should be included in templates
    ALLOWED_HIDDEN_DIRS = {".github"}

    def _is_hidden(self, name: str) -> bool:
        """Check if a file or directory name is hidden (starts with dot).

        Hidden files/directories are skipped during template processing,
        except for explicitly allowed directories like .github.

        Args:
            name: The file or directory name to check.

        Returns:
            True if the name starts with '.' and is not in ALLOWED_HIDDEN_DIRS,
            False otherwise.
        """
        if name.startswith("."):
            return name not in self.ALLOWED_HIDDEN_DIRS
        return False

    def render(
        self, output_dir: Path, variables: dict[str, str], force: bool = False
    ) -> list[Path]:
        """Render all templates to the output directory.

        Recursively walks the template directory, substitutes variables in both
        file/directory names and file contents, and writes the processed files
        to the output directory.

        Args:
            output_dir: Target directory for rendered files.
            variables: Dictionary of template variables to substitute.
            force: Whether to overwrite existing files. If False, existing
                   files are skipped.

        Returns:
            List of created file paths (relative to output_dir).

        Raises:
            TemplateError: If a required variable is missing or template is invalid.
        """
        created_files: list[Path] = []

        # Walk the template directory recursively
        for template_path in self.template_dir.rglob("*"):
            # Get the relative path from template directory
            rel_path = template_path.relative_to(self.template_dir)

            # Skip hidden files and directories
            if any(self._is_hidden(part) for part in rel_path.parts):
                continue

            # Skip directories (we'll create them when writing files)
            if template_path.is_dir():
                continue

            # Substitute variables in the path
            output_rel_path_str = self._substitute_path(str(rel_path), variables)
            output_path = output_dir / output_rel_path_str

            # Check if file exists and handle force flag
            if output_path.exists() and not force:
                continue

            # Create parent directories
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Handle binary vs text files
            if self._is_binary_file(template_path):
                # Copy binary files as-is
                output_path.write_bytes(template_path.read_bytes())
            else:
                # Read, substitute, and write text files
                content = template_path.read_text(encoding="utf-8")
                substituted_content = self._substitute_content(content, variables)
                output_path.write_text(substituted_content, encoding="utf-8")

            created_files.append(Path(output_rel_path_str))

        return created_files
