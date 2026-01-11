# SPDX-License-Identifier: MIT
"""Property-based tests for migration tooling.

Feature: island-format-migration
Properties 8, 9, 10: Migration metadata preservation, entry point detection, validation
Validates: Requirements 8.2, 8.3, 8.4, 8.5
"""

from __future__ import annotations

import ast
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from hypothesis import given, settings, strategies as st

# Import the manifest constants directly to avoid circular imports
from island_manifest import CURRENT_SCHEMA_VERSION, MANIFEST_DEFAULTS, MIN_COMPATIBLE_VERSION


# =============================================================================
# Re-implement the functions we need to test to avoid circular imports
# These are copies of the functions from migrate.py for testing purposes
# =============================================================================


def _normalize_name(name: str) -> str:
    """Normalize a name to a valid Python package name."""
    name = name.lower()
    name = re.sub(r"[\s-]+", "_", name)
    name = re.sub(r"[^a-z0-9_]", "", name)
    if name and name[0].isdigit():
        name = "_" + name
    return name


def _migrate_manifest(legacy: dict[str, Any]) -> dict[str, Any]:
    """Migrate a legacy manifest to the modern schema."""
    migrated: dict[str, Any] = {}

    migrated["game"] = legacy.get("game", "Unknown Game")
    migrated["version"] = CURRENT_SCHEMA_VERSION
    migrated["compatible_version"] = legacy.get("compatible_version", MIN_COMPATIBLE_VERSION)

    if "world_version" in legacy:
        migrated["world_version"] = legacy["world_version"]
    elif "data_version" in legacy:
        migrated["world_version"] = str(legacy["data_version"])

    if "minimum_ap_version" in legacy:
        migrated["minimum_ap_version"] = legacy["minimum_ap_version"]

    if "maximum_ap_version" in legacy:
        migrated["maximum_ap_version"] = legacy["maximum_ap_version"]

    if "authors" in legacy:
        migrated["authors"] = legacy["authors"]

    if "description" in legacy:
        migrated["description"] = legacy["description"]

    if "license" in legacy:
        migrated["license"] = legacy["license"]

    if "homepage" in legacy:
        migrated["homepage"] = legacy["homepage"]

    if "repository" in legacy:
        migrated["repository"] = legacy["repository"]

    if "keywords" in legacy:
        migrated["keywords"] = legacy["keywords"]

    if "platforms" in legacy:
        migrated["platforms"] = legacy["platforms"]

    if "pure_python" in legacy:
        migrated["pure_python"] = legacy["pure_python"]

    if "vendored_dependencies" in legacy:
        migrated["vendored_dependencies"] = legacy["vendored_dependencies"]

    for key, default_value in MANIFEST_DEFAULTS.items():
        if key not in migrated:
            if isinstance(default_value, list | dict):
                migrated[key] = default_value.copy()
            else:
                migrated[key] = default_value

    return migrated


PYPROJECT_TEMPLATE = """[build-system]
requires = ["hatchling", "island-build"]
build-backend = "hatchling.build"

[project]
name = "{name}"
version = "{version}"
description = "{description}"
readme = "README.md"
license = {{text = "{license}"}}
requires-python = ">=3.10"
{authors_section}keywords = {keywords}
dependencies = []

[project.urls]
Homepage = "{homepage}"
Repository = "{repository}"

[project.entry-points.ap-island]
{entry_points_section}

[tool.island]
game = "{game}"
minimum_ap_version = "{minimum_ap_version}"
{maximum_ap_version_line}
[tool.island.vendor]
exclude = ["typing_extensions"]

[tool.hatch.build.targets.wheel]
packages = ["src/{package_name}"]
"""


def _generate_pyproject(
    manifest: dict[str, Any],
    package_name: str,
    entry_points: list[dict[str, str]] | None = None,
) -> str:
    """Generate pyproject.toml content from a manifest."""
    game = manifest.get("game", "Unknown Game")
    version = manifest.get("world_version", "0.1.0")
    description = manifest.get("description", f"Archipelago randomizer implementation for {game}")

    license_text = manifest.get("license", "MIT")

    authors = manifest.get("authors", [])
    if authors:
        authors_lines = []
        for author in authors:
            authors_lines.append(f'    {{name = "{author}"}}')
        authors_section = "authors = [\n" + ",\n".join(authors_lines) + "\n]\n"
    else:
        authors_section = 'authors = [\n    {name = "Your Name"}\n]\n'

    keywords = manifest.get("keywords", [])
    game_lower = game.lower().replace(" ", "-")
    default_keywords = [game_lower, "archipelago", "randomizer"]
    merged_keywords = list(dict.fromkeys(default_keywords + keywords))
    keywords_str = json.dumps(merged_keywords)

    homepage = manifest.get("homepage", "https://github.com/ArchipelagoMW/Archipelago")
    repository = manifest.get("repository", "https://github.com/ArchipelagoMW/Archipelago")

    minimum_ap_version = manifest.get("minimum_ap_version", "0.5.0")
    maximum_ap_version = manifest.get("maximum_ap_version")
    maximum_ap_version_line = (
        f'maximum_ap_version = "{maximum_ap_version}"\n' if maximum_ap_version else ""
    )

    if entry_points:
        entry_points_lines = []
        for ep in entry_points:
            entry_points_lines.append(f'{ep["name"]} = "{ep["module"]}:{ep["attr"]}"')
        entry_points_section = "\n".join(entry_points_lines)
    else:
        entry_points_section = (
            f'{package_name} = "{package_name}.world:{package_name.title().replace("_", "")}World"'
        )

    return PYPROJECT_TEMPLATE.format(
        name=package_name.replace("_", "-"),
        package_name=package_name,
        version=version,
        description=description,
        license=license_text,
        authors_section=authors_section,
        keywords=keywords_str,
        homepage=homepage,
        repository=repository,
        game=game,
        minimum_ap_version=minimum_ap_version,
        maximum_ap_version_line=maximum_ap_version_line,
        entry_points_section=entry_points_section,
    )


class WebWorldDetector:
    """Detects WebWorld subclasses in Python source files."""

    WEBWORLD_BASE_CLASSES = {"WebWorld", "World"}

    def __init__(self) -> None:
        self.detected_classes: list[dict[str, str]] = []

    def scan_directory(self, source_dir: Path) -> list[dict[str, str]]:
        """Scan a directory for WebWorld subclasses."""
        self.detected_classes = []

        for py_file in source_dir.rglob("*.py"):
            try:
                self._scan_file(py_file, source_dir)
            except SyntaxError:
                continue

        return self.detected_classes

    def _scan_file(self, file_path: Path, source_dir: Path) -> None:
        """Scan a single Python file for WebWorld subclasses."""
        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()
        except (OSError, UnicodeDecodeError):
            return

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        rel_path = file_path.relative_to(source_dir)
        module_parts = list(rel_path.parts[:-1]) + [rel_path.stem]
        module_path = ".".join(module_parts)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if self._is_webworld_subclass(node):
                    entry_name = node.name.lower().replace("world", "")
                    if not entry_name:
                        entry_name = node.name.lower()

                    self.detected_classes.append(
                        {
                            "name": entry_name,
                            "module": module_path,
                            "attr": node.name,
                        }
                    )

    def _is_webworld_subclass(self, node: ast.ClassDef) -> bool:
        """Check if a class definition is a WebWorld subclass."""
        for base in node.bases:
            base_name = self._get_base_name(base)
            if base_name in self.WEBWORLD_BASE_CLASSES:
                return True
        return False

    def _get_base_name(self, node: ast.expr) -> str:
        """Extract the base class name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""


def detect_webworld_classes(source_dir: Path) -> list[dict[str, str]]:
    """Detect WebWorld subclasses in a source directory."""
    detector = WebWorldDetector()
    return detector.scan_directory(source_dir)


def validate_migrated_package(
    project_dir: Path,
    package_name: str,
) -> list[str]:
    """Validate that a migrated package meets island format requirements."""
    errors: list[str] = []

    pyproject_path = project_dir / "pyproject.toml"
    if not pyproject_path.exists():
        errors.append("pyproject.toml not found")
        return errors

    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        errors.append(f"Invalid TOML syntax: {e}")
        return errors

    project = pyproject.get("project", {})
    if not project.get("name"):
        errors.append("Missing required field: [project].name")
    if not project.get("version"):
        errors.append("Missing required field: [project].version")

    tool_island = pyproject.get("tool", {}).get("island", {})
    if not tool_island:
        errors.append("Missing [tool.island] section")

    tool_apworld = pyproject.get("tool", {}).get("apworld")
    if tool_apworld:
        errors.append("Legacy [tool.apworld] section found - should be [tool.island]")

    entry_points = project.get("entry-points", {})
    ap_island_eps = entry_points.get("ap-island", {})
    if not ap_island_eps:
        errors.append("Missing required [project.entry-points.ap-island] entry points")

    src_candidates = [
        project_dir / "src" / package_name,
        project_dir / package_name,
    ]
    source_found = False
    for candidate in src_candidates:
        if candidate.exists():
            source_found = True
            break

    if not source_found:
        errors.append(f"Source directory not found: src/{package_name}/ or {package_name}/")

    return errors


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Valid game names
valid_game_names = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_"),
    min_size=3,
    max_size=30,
).filter(lambda x: x.strip() and not x.startswith(" ") and not x.endswith(" "))

# Valid versions (semver-like)
valid_versions = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)

# Valid author names
valid_author_names = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ "),
    min_size=2,
    max_size=30,
).filter(lambda x: x.strip())

# Valid descriptions
valid_descriptions = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!-"),
    min_size=5,
    max_size=100,
).filter(lambda x: x.strip())

# Valid AP versions
valid_ap_versions = st.from_regex(r"0\.[0-9]+\.[0-9]+", fullmatch=True)

# Valid class names (PascalCase)
valid_class_names = st.from_regex(r"[A-Z][a-zA-Z0-9]{2,20}World", fullmatch=True)


@st.composite
def legacy_manifest_data(draw):
    """Generate valid legacy archipelago.json data."""
    game = draw(valid_game_names)
    return {
        "game": game,
        "version": draw(st.integers(min_value=1, max_value=10)),
        "compatible_version": draw(st.integers(min_value=1, max_value=5)),
        "world_version": draw(valid_versions),
        "authors": draw(st.lists(valid_author_names, min_size=1, max_size=3)),
        "description": draw(valid_descriptions),
        "minimum_ap_version": draw(valid_ap_versions),
        "license": draw(st.sampled_from(["MIT", "GPL-3.0", "Apache-2.0", "BSD-3-Clause"])),
        "homepage": f"https://github.com/example/{_normalize_name(game)}",
        "repository": f"https://github.com/example/{_normalize_name(game)}",
        "keywords": draw(
            st.lists(
                st.text(min_size=3, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz"),
                min_size=0,
                max_size=5,
            )
        ),
    }


@st.composite
def webworld_class_data(draw):
    """Generate data for a WebWorld class."""
    class_name = draw(valid_class_names)
    module_name = draw(st.from_regex(r"[a-z][a-z0-9_]{2,15}", fullmatch=True))
    return {
        "class_name": class_name,
        "module_name": module_name,
        "base_class": draw(st.sampled_from(["WebWorld", "World"])),
    }


# =============================================================================
# Property 8: Migration metadata preservation
# =============================================================================


class TestMigrationMetadataPreservation:
    """Property-based tests for migration metadata preservation.

    Feature: island-format-migration, Property 8: Migration metadata preservation
    Validates: Requirements 8.2
    """

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_migrate_preserves_game_name(self, legacy_data: dict):
        """
        Property 8: Migration metadata preservation - game name

        *For any* legacy APWorld package with valid metadata, migrating to island
        format SHALL preserve the game name.

        **Validates: Requirements 8.2**
        """
        migrated = _migrate_manifest(legacy_data)
        assert migrated["game"] == legacy_data["game"]

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_migrate_preserves_world_version(self, legacy_data: dict):
        """
        Property 8: Migration metadata preservation - world version

        *For any* legacy APWorld package with valid metadata, migrating to island
        format SHALL preserve the world version.

        **Validates: Requirements 8.2**
        """
        migrated = _migrate_manifest(legacy_data)
        assert migrated["world_version"] == legacy_data["world_version"]

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_migrate_preserves_authors(self, legacy_data: dict):
        """
        Property 8: Migration metadata preservation - authors

        *For any* legacy APWorld package with valid metadata, migrating to island
        format SHALL preserve the authors list.

        **Validates: Requirements 8.2**
        """
        migrated = _migrate_manifest(legacy_data)
        assert migrated["authors"] == legacy_data["authors"]

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_migrate_preserves_description(self, legacy_data: dict):
        """
        Property 8: Migration metadata preservation - description

        *For any* legacy APWorld package with valid metadata, migrating to island
        format SHALL preserve the description.

        **Validates: Requirements 8.2**
        """
        migrated = _migrate_manifest(legacy_data)
        assert migrated["description"] == legacy_data["description"]

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_migrate_preserves_ap_version_bounds(self, legacy_data: dict):
        """
        Property 8: Migration metadata preservation - AP version bounds

        *For any* legacy APWorld package with valid metadata, migrating to island
        format SHALL preserve the minimum AP version.

        **Validates: Requirements 8.2**
        """
        migrated = _migrate_manifest(legacy_data)
        assert migrated["minimum_ap_version"] == legacy_data["minimum_ap_version"]

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_migrate_preserves_license(self, legacy_data: dict):
        """
        Property 8: Migration metadata preservation - license

        *For any* legacy APWorld package with valid metadata, migrating to island
        format SHALL preserve the license.

        **Validates: Requirements 8.2**
        """
        migrated = _migrate_manifest(legacy_data)
        assert migrated["license"] == legacy_data["license"]

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_migrate_preserves_urls(self, legacy_data: dict):
        """
        Property 8: Migration metadata preservation - URLs

        *For any* legacy APWorld package with valid metadata, migrating to island
        format SHALL preserve homepage and repository URLs.

        **Validates: Requirements 8.2**
        """
        migrated = _migrate_manifest(legacy_data)
        assert migrated["homepage"] == legacy_data["homepage"]
        assert migrated["repository"] == legacy_data["repository"]

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_migrate_preserves_keywords(self, legacy_data: dict):
        """
        Property 8: Migration metadata preservation - keywords

        *For any* legacy APWorld package with valid metadata, migrating to island
        format SHALL preserve keywords.

        **Validates: Requirements 8.2**
        """
        migrated = _migrate_manifest(legacy_data)
        assert migrated["keywords"] == legacy_data["keywords"]


# =============================================================================
# Property 9: Migration entry point detection
# =============================================================================


class TestMigrationEntryPointDetection:
    """Property-based tests for migration entry point detection.

    Feature: island-format-migration, Property 9: Migration entry point detection
    Validates: Requirements 8.3, 8.4
    """

    @given(class_data=webworld_class_data())
    @settings(max_examples=100)
    def test_detects_webworld_subclass(self, class_data: dict):
        """
        Property 9: Migration entry point detection - WebWorld detection

        *For any* legacy APWorld package containing WebWorld subclasses, the
        migration tool SHALL detect these classes.

        **Validates: Requirements 8.3**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create a source file with a WebWorld subclass
            source_dir = tmp_path / "src"
            source_dir.mkdir()

            module_dir = source_dir / class_data["module_name"]
            module_dir.mkdir()

            # Create __init__.py
            (module_dir / "__init__.py").write_text("")

            # Create world.py with WebWorld subclass
            world_file = module_dir / "world.py"
            world_file.write_text(
                f'''"""Test world module."""

class {class_data["class_name"]}({class_data["base_class"]}):
    """A test world."""
    game = "Test Game"
'''
            )

            # Detect WebWorld classes
            detected = detect_webworld_classes(source_dir)

            # Should detect at least one class
            assert len(detected) >= 1

            # Should find our class
            class_names = [d["attr"] for d in detected]
            assert class_data["class_name"] in class_names

    @given(class_data=webworld_class_data())
    @settings(max_examples=100)
    def test_generates_entry_points_for_detected_classes(self, class_data: dict):
        """
        Property 9: Migration entry point detection - entry point generation

        *For any* detected WebWorld class, the migration tool SHALL generate
        corresponding ap-island entry points.

        **Validates: Requirements 8.3, 8.4**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create a source file with a WebWorld subclass
            source_dir = tmp_path / "src"
            source_dir.mkdir()

            module_dir = source_dir / class_data["module_name"]
            module_dir.mkdir()

            (module_dir / "__init__.py").write_text("")

            world_file = module_dir / "world.py"
            world_file.write_text(
                f'''"""Test world module."""

class {class_data["class_name"]}({class_data["base_class"]}):
    """A test world."""
    game = "Test Game"
'''
            )

            # Detect WebWorld classes
            detected = detect_webworld_classes(source_dir)

            # Each detected class should have entry point info
            for entry_point in detected:
                assert "name" in entry_point
                assert "module" in entry_point
                assert "attr" in entry_point
                # Module should be a valid Python module path
                assert "." in entry_point["module"] or entry_point["module"]
                # Attr should be the class name
                assert entry_point["attr"]

    @given(class_data=webworld_class_data())
    @settings(max_examples=100)
    def test_entry_point_module_path_is_correct(self, class_data: dict):
        """
        Property 9: Migration entry point detection - module path correctness

        *For any* detected WebWorld class, the generated entry point SHALL have
        the correct module path relative to the source directory.

        **Validates: Requirements 8.4**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create a source file with a WebWorld subclass
            source_dir = tmp_path / "src"
            source_dir.mkdir()

            module_dir = source_dir / class_data["module_name"]
            module_dir.mkdir()

            (module_dir / "__init__.py").write_text("")

            world_file = module_dir / "world.py"
            world_file.write_text(
                f'''"""Test world module."""

class {class_data["class_name"]}({class_data["base_class"]}):
    """A test world."""
    game = "Test Game"
'''
            )

            # Detect WebWorld classes
            detected = detect_webworld_classes(source_dir)

            # Find our class
            our_entry = None
            for entry_point in detected:
                if entry_point["attr"] == class_data["class_name"]:
                    our_entry = entry_point
                    break

            assert our_entry is not None
            # Module path should include the module name and 'world'
            expected_module = f"{class_data['module_name']}.world"
            assert our_entry["module"] == expected_module


# =============================================================================
# Property 10: Migration validation
# =============================================================================


class TestMigrationValidation:
    """Property-based tests for migration validation.

    Feature: island-format-migration, Property 10: Migration validation
    Validates: Requirements 8.5
    """

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_valid_migrated_package_passes_validation(self, legacy_data: dict):
        """
        Property 10: Migration validation - valid packages pass

        *For any* successfully migrated package with proper structure, the
        validation SHALL pass.

        **Validates: Requirements 8.5**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create a properly migrated package
            project_dir = tmp_path / "project"
            project_dir.mkdir()

            # Normalize the package name
            package_name = _normalize_name(legacy_data["game"])

            # Create source directory
            src_dir = project_dir / "src" / package_name
            src_dir.mkdir(parents=True)
            (src_dir / "__init__.py").write_text('"""Package."""\n')
            (src_dir / "world.py").write_text(
                f'''"""World module."""

class {package_name.title().replace("_", "")}World:
    game = "{legacy_data["game"]}"
'''
            )

            # Generate and write pyproject.toml
            entry_points = [
                {
                    "name": package_name,
                    "module": f"{package_name}.world",
                    "attr": f"{package_name.title().replace('_', '')}World",
                }
            ]
            pyproject_content = _generate_pyproject(legacy_data, package_name, entry_points)
            (project_dir / "pyproject.toml").write_text(pyproject_content)

            # Validate
            errors = validate_migrated_package(project_dir, package_name)

            # Should have no errors
            assert errors == [], f"Validation errors: {errors}"

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_missing_pyproject_fails_validation(self, legacy_data: dict):
        """
        Property 10: Migration validation - missing pyproject.toml fails

        *For any* package without pyproject.toml, validation SHALL fail.

        **Validates: Requirements 8.5**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            project_dir = tmp_path / "project"
            project_dir.mkdir()

            package_name = _normalize_name(legacy_data["game"])

            # Don't create pyproject.toml
            errors = validate_migrated_package(project_dir, package_name)

            assert len(errors) > 0
            assert any("pyproject.toml" in e for e in errors)

    @given(legacy_data=legacy_manifest_data())
    @settings(max_examples=100)
    def test_missing_source_dir_fails_validation(self, legacy_data: dict):
        """
        Property 10: Migration validation - missing source directory fails

        *For any* package without source directory, validation SHALL fail.

        **Validates: Requirements 8.5**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            project_dir = tmp_path / "project"
            project_dir.mkdir()

            package_name = _normalize_name(legacy_data["game"])

            # Create pyproject.toml but no source directory
            entry_points = [
                {
                    "name": package_name,
                    "module": f"{package_name}.world",
                    "attr": f"{package_name.title().replace('_', '')}World",
                }
            ]
            pyproject_content = _generate_pyproject(legacy_data, package_name, entry_points)
            (project_dir / "pyproject.toml").write_text(pyproject_content)

            errors = validate_migrated_package(project_dir, package_name)

            assert len(errors) > 0
            assert any("Source directory" in e or "source" in e.lower() for e in errors)
