# SPDX-License-Identifier: MIT
"""Tests for the template engine."""

from __future__ import annotations

import string
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from apworld_cli.template_engine import TemplateEngine


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def template_dir(tmp_path: Path) -> Path:
    """Create a temporary template directory."""
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()
    return tpl_dir


@pytest.fixture
def engine(template_dir: Path) -> TemplateEngine:
    """Create a TemplateEngine instance."""
    return TemplateEngine(template_dir)


# =============================================================================
# Property-Based Tests
# =============================================================================

# Strategy for valid variable names (alphanumeric + underscore, starting with letter)
var_name_strategy = st.text(
    alphabet=string.ascii_lowercase + string.digits + "_",
    min_size=1,
    max_size=20,
).filter(lambda s: s[0].isalpha())

# Strategy for variable values (printable strings without braces to avoid confusion)
var_value_strategy = st.text(
    alphabet=string.ascii_letters + string.digits + " _-.",
    min_size=0,
    max_size=50,
)


# Feature: init-template-refactor, Property 1: Variable Substitution in Content
# **Validates: Requirements 2.1**
@given(
    variables=st.dictionaries(
        keys=var_name_strategy,
        values=var_value_strategy,
        min_size=1,
        max_size=5,
    )
)
@settings(max_examples=100)
def test_variable_substitution_replaces_all_patterns(variables: dict[str, str]) -> None:
    """For any variables dict, substitution replaces all {{variable}} patterns.

    Property 1: Variable Substitution in Content
    For any template string containing {{variable}} patterns and a variables
    dictionary containing all referenced variables, substituting the template
    SHALL produce a string where all {{variable}} occurrences are replaced
    with their corresponding values.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        template_dir = Path(tmp_dir)
        engine = TemplateEngine(template_dir)

        # Build a template string using all variables
        template_parts = []
        for var_name in variables:
            template_parts.append("prefix_{{" + var_name + "}}_suffix")

        template = " ".join(template_parts)

        # Substitute
        result = engine._substitute_content(template, variables)

        # Verify all variables were substituted
        for var_name, var_value in variables.items():
            assert f"prefix_{var_value}_suffix" in result
            assert f"{{{{{var_name}}}}}" not in result  # No remaining patterns


# Feature: init-template-refactor, Property 1: Variable Substitution in Content
# **Validates: Requirements 2.1**
@given(
    var_name=var_name_strategy,
    var_value=var_value_strategy,
    prefix=st.text(alphabet=string.ascii_letters, min_size=0, max_size=10),
    suffix=st.text(alphabet=string.ascii_letters, min_size=0, max_size=10),
)
@settings(max_examples=100)
def test_variable_substitution_preserves_surrounding_text(
    var_name: str, var_value: str, prefix: str, suffix: str
) -> None:
    """Substitution preserves text before and after the variable pattern."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        template_dir = Path(tmp_dir)
        engine = TemplateEngine(template_dir)

        template = prefix + "{{" + var_name + "}}" + suffix
        variables = {var_name: var_value}

        result = engine._substitute_content(template, variables)

        assert result == f"{prefix}{var_value}{suffix}"


# Feature: init-template-refactor, Property 2: Path Substitution
# **Validates: Requirements 2.2, 2.3**
@given(
    var_name=var_name_strategy,
    var_value=st.text(
        alphabet=string.ascii_letters + string.digits + "_",
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=100)
def test_path_substitution_replaces_directory_names(var_name: str, var_value: str) -> None:
    """For any path with {{variable}} patterns, substitution produces valid paths.

    Property 2: Path Substitution
    For any file or directory path containing {{variable}} patterns and a
    variables dictionary, the substituted path SHALL have all variable patterns
    replaced with their corresponding values, producing a valid path string.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        template_dir = Path(tmp_dir)
        engine = TemplateEngine(template_dir)

        # Test directory name substitution
        path = "src/{{" + var_name + "}}/module.py"
        variables = {var_name: var_value}

        result = engine._substitute_path(path, variables)

        assert result == f"src/{var_value}/module.py"
        assert "{{" not in result
        assert "}}" not in result


# Feature: init-template-refactor, Property 2: Path Substitution
# **Validates: Requirements 2.2, 2.3**
@given(
    var_name=var_name_strategy,
    var_value=st.text(
        alphabet=string.ascii_letters + string.digits + "_",
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=100)
def test_path_substitution_replaces_file_names(var_name: str, var_value: str) -> None:
    """For any filename with {{variable}} patterns, substitution produces valid filenames."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        template_dir = Path(tmp_dir)
        engine = TemplateEngine(template_dir)

        # Test filename substitution
        path = "{{" + var_name + "}}.py"
        variables = {var_name: var_value}

        result = engine._substitute_path(path, variables)

        assert result == f"{var_value}.py"
        assert "{{" not in result
        assert "}}" not in result


# Feature: init-template-refactor, Property 2: Path Substitution
# **Validates: Requirements 2.2, 2.3**
@given(
    var_names=st.lists(var_name_strategy, min_size=2, max_size=3, unique=True),
    var_values=st.lists(
        st.text(alphabet=string.ascii_letters + string.digits + "_", min_size=1, max_size=10),
        min_size=2,
        max_size=3,
    ),
)
@settings(max_examples=100)
def test_path_substitution_handles_multiple_variables(
    var_names: list[str], var_values: list[str]
) -> None:
    """Path substitution handles multiple variables in a single path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        template_dir = Path(tmp_dir)
        engine = TemplateEngine(template_dir)

        # Ensure we have matching lengths
        var_names = var_names[: len(var_values)]
        var_values = var_values[: len(var_names)]

        if not var_names:
            return

        # Build path with multiple variables
        path_parts = ["/{{" + name + "}}" for name in var_names]
        path = "".join(path_parts) + "/file.py"

        variables = dict(zip(var_names, var_values))

        result = engine._substitute_path(path, variables)

        # Verify all variables were substituted
        for value in var_values:
            assert f"/{value}" in result or result.startswith(value)
        assert "{{" not in result
        assert "}}" not in result


# Feature: init-template-refactor, Property 3: Undefined Variable Error
# **Validates: Requirements 2.4**
@given(
    undefined_var=var_name_strategy,
    defined_vars=st.dictionaries(
        keys=var_name_strategy,
        values=var_value_strategy,
        min_size=0,
        max_size=3,
    ),
)
@settings(max_examples=100)
def test_undefined_variable_raises_template_error(
    undefined_var: str, defined_vars: dict[str, str]
) -> None:
    """For any undefined variable, substitution raises TemplateError.

    Property 3: Undefined Variable Error
    For any template string containing a {{variable}} pattern where the variable
    is not present in the variables dictionary, the template engine SHALL raise
    a TemplateError with a message identifying the undefined variable.
    """
    # Import here to avoid issues with module loading
    from apworld_cli.template_engine import TemplateError

    with tempfile.TemporaryDirectory() as tmp_dir:
        template_dir = Path(tmp_dir)
        engine = TemplateEngine(template_dir)

        # Ensure the undefined variable is not in the defined vars
        if undefined_var in defined_vars:
            del defined_vars[undefined_var]

        # Create a template with the undefined variable
        template = "Hello {{" + undefined_var + "}}!"

        # Should raise TemplateError
        with pytest.raises(TemplateError) as exc_info:
            engine._substitute_content(template, defined_vars)

        # Error message should identify the undefined variable
        assert undefined_var in str(exc_info.value)


# Feature: init-template-refactor, Property 3: Undefined Variable Error
# **Validates: Requirements 2.4**
@given(
    undefined_var=var_name_strategy,
)
@settings(max_examples=100)
def test_undefined_variable_in_path_raises_template_error(undefined_var: str) -> None:
    """For any undefined variable in a path, substitution raises TemplateError."""
    from apworld_cli.template_engine import TemplateError

    with tempfile.TemporaryDirectory() as tmp_dir:
        template_dir = Path(tmp_dir)
        engine = TemplateEngine(template_dir)

        # Create a path with the undefined variable
        path = "src/{{" + undefined_var + "}}/module.py"

        # Should raise TemplateError with empty variables dict
        with pytest.raises(TemplateError) as exc_info:
            engine._substitute_path(path, {})

        # Error message should identify the undefined variable
        assert undefined_var in str(exc_info.value)


# =============================================================================
# Property Tests for render() method
# =============================================================================


# Feature: init-template-refactor, Property 4: Template-to-Output Mapping
# **Validates: Requirements 1.1, 1.3, 5.2**
@given(
    file_names=st.lists(
        st.text(
            alphabet=string.ascii_lowercase + string.digits + "_",
            min_size=1,
            max_size=10,
        ),
        min_size=1,
        max_size=5,
        unique=True,
    ),
    var_name=var_name_strategy,
    var_value=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
)
@settings(max_examples=100)
def test_render_creates_output_for_each_template_file(
    file_names: list[str], var_name: str, var_value: str
) -> None:
    """For any template directory, rendering produces corresponding output files.

    Property 4: Template-to-Output Mapping
    For any template directory structure and valid variables dictionary, rendering
    SHALL produce an output directory where every non-hidden file in the template
    directory has a corresponding file in the output directory at the path-substituted
    location.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        template_dir = tmp_path / "templates"
        output_dir = tmp_path / "output"
        template_dir.mkdir()

        # Create template files with variable in content
        for file_name in file_names:
            template_file = template_dir / f"{file_name}.txt"
            template_file.write_text(f"Content with {{{{{var_name}}}}}")

        engine = TemplateEngine(template_dir)
        variables = {var_name: var_value}

        created_files = engine.render(output_dir, variables)

        # Verify each template file has a corresponding output file
        assert len(created_files) == len(file_names)
        for file_name in file_names:
            output_file = output_dir / f"{file_name}.txt"
            assert output_file.exists()
            assert f"Content with {var_value}" in output_file.read_text()


# Feature: init-template-refactor, Property 4: Template-to-Output Mapping
# **Validates: Requirements 1.1, 1.3, 5.2**
@given(
    dir_name=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
    file_name=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
    var_name=var_name_strategy,
    var_value=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
)
@settings(max_examples=100)
def test_render_substitutes_variables_in_paths(
    dir_name: str, file_name: str, var_name: str, var_value: str
) -> None:
    """Rendering substitutes variables in directory and file names."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        template_dir = tmp_path / "templates"
        output_dir = tmp_path / "output"

        # Create nested template structure with variable in path
        nested_dir = template_dir / f"{dir_name}" / f"{{{{{var_name}}}}}"
        nested_dir.mkdir(parents=True)
        template_file = nested_dir / f"{file_name}.txt"
        template_file.write_text("content")

        engine = TemplateEngine(template_dir)
        variables = {var_name: var_value}

        engine.render(output_dir, variables)

        # Verify the output path has substituted variable
        expected_output = output_dir / dir_name / var_value / f"{file_name}.txt"
        assert expected_output.exists()


# Feature: init-template-refactor, Property 5: Force Overwrite Behavior
# **Validates: Requirements 4.4**
@given(
    file_name=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
    original_content=st.text(
        alphabet=string.ascii_letters + string.digits + " ",
        min_size=1,
        max_size=50,
    ),
    new_content=st.text(
        alphabet=string.ascii_letters + string.digits + " ",
        min_size=1,
        max_size=50,
    ),
)
@settings(max_examples=100)
def test_render_with_force_overwrites_existing_files(
    file_name: str, original_content: str, new_content: str
) -> None:
    """With force=True, rendering overwrites existing files.

    Property 5: Force Overwrite Behavior
    For any output directory containing existing files and force=True, rendering
    SHALL overwrite all conflicting files.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        template_dir = tmp_path / "templates"
        output_dir = tmp_path / "output"
        template_dir.mkdir()
        output_dir.mkdir()

        # Create template file
        template_file = template_dir / f"{file_name}.txt"
        template_file.write_text(new_content)

        # Create existing output file with different content
        existing_file = output_dir / f"{file_name}.txt"
        existing_file.write_text(original_content)

        engine = TemplateEngine(template_dir)

        # Render with force=True
        engine.render(output_dir, {}, force=True)

        # Verify file was overwritten
        assert existing_file.read_text() == new_content


# Feature: init-template-refactor, Property 5: Force Overwrite Behavior
# **Validates: Requirements 4.4**
@given(
    file_name=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
    original_content=st.text(
        alphabet=string.ascii_letters + string.digits + " ",
        min_size=1,
        max_size=50,
    ),
    new_content=st.text(
        alphabet=string.ascii_letters + string.digits + " ",
        min_size=1,
        max_size=50,
    ),
)
@settings(max_examples=100)
def test_render_without_force_skips_existing_files(
    file_name: str, original_content: str, new_content: str
) -> None:
    """With force=False, rendering does not modify existing files.

    Property 5: Force Overwrite Behavior
    Conversely, with force=False, rendering SHALL not modify existing files.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        template_dir = tmp_path / "templates"
        output_dir = tmp_path / "output"
        template_dir.mkdir()
        output_dir.mkdir()

        # Create template file
        template_file = template_dir / f"{file_name}.txt"
        template_file.write_text(new_content)

        # Create existing output file with different content
        existing_file = output_dir / f"{file_name}.txt"
        existing_file.write_text(original_content)

        engine = TemplateEngine(template_dir)

        # Render with force=False (default)
        created_files = engine.render(output_dir, {}, force=False)

        # Verify file was NOT overwritten
        assert existing_file.read_text() == original_content
        # Verify the file was not in the created files list
        assert Path(f"{file_name}.txt") not in created_files


# Feature: init-template-refactor, Property 6: Hidden File Exclusion
# **Validates: Requirements 5.3**
@given(
    hidden_name=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
    visible_name=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
)
@settings(max_examples=100)
def test_render_excludes_hidden_files(hidden_name: str, visible_name: str) -> None:
    """Rendering excludes hidden files (names starting with dot).

    Property 6: Hidden File Exclusion
    For any template directory containing hidden files or directories (names
    starting with '.'), rendering SHALL NOT include these in the output directory.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        template_dir = tmp_path / "templates"
        output_dir = tmp_path / "output"
        template_dir.mkdir()

        # Create a hidden file
        hidden_file = template_dir / f".{hidden_name}"
        hidden_file.write_text("hidden content")

        # Create a visible file
        visible_file = template_dir / f"{visible_name}.txt"
        visible_file.write_text("visible content")

        engine = TemplateEngine(template_dir)
        created_files = engine.render(output_dir, {})

        # Verify hidden file was NOT created
        assert not (output_dir / f".{hidden_name}").exists()
        # Verify visible file WAS created
        assert (output_dir / f"{visible_name}.txt").exists()
        # Verify only visible file is in created files list
        assert len(created_files) == 1
        assert Path(f"{visible_name}.txt") in created_files


# Feature: init-template-refactor, Property 6: Hidden File Exclusion
# **Validates: Requirements 5.3**
@given(
    hidden_dir_name=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
    file_name=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
)
@settings(max_examples=100)
def test_render_excludes_files_in_hidden_directories(hidden_dir_name: str, file_name: str) -> None:
    """Rendering excludes files inside hidden directories."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        template_dir = tmp_path / "templates"
        output_dir = tmp_path / "output"
        template_dir.mkdir()

        # Create a file inside a hidden directory
        hidden_dir = template_dir / f".{hidden_dir_name}"
        hidden_dir.mkdir()
        hidden_file = hidden_dir / f"{file_name}.txt"
        hidden_file.write_text("content in hidden dir")

        engine = TemplateEngine(template_dir)
        created_files = engine.render(output_dir, {})

        # Verify no files were created (the only file is in a hidden dir)
        assert len(created_files) == 0
        assert not (output_dir / f".{hidden_dir_name}").exists()


# Feature: init-template-refactor, Property 7: Binary File Preservation
# **Validates: Requirements 5.4**
@given(
    file_name=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
    binary_content=st.binary(min_size=1, max_size=1000),
)
@settings(max_examples=100)
def test_render_preserves_binary_files_byte_for_byte(file_name: str, binary_content: bytes) -> None:
    """Binary files are copied without modification.

    Property 7: Binary File Preservation
    For any binary file in the template directory, rendering SHALL copy the file
    to the output directory without modification (byte-for-byte identical).
    """
    # Ensure the content contains a null byte to be detected as binary
    binary_content_with_null = binary_content + b"\x00"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        template_dir = tmp_path / "templates"
        output_dir = tmp_path / "output"
        template_dir.mkdir()

        # Create a binary file
        binary_file = template_dir / f"{file_name}.bin"
        binary_file.write_bytes(binary_content_with_null)

        engine = TemplateEngine(template_dir)
        engine.render(output_dir, {})

        # Verify binary file was copied byte-for-byte
        output_file = output_dir / f"{file_name}.bin"
        assert output_file.exists()
        assert output_file.read_bytes() == binary_content_with_null


# Feature: init-template-refactor, Property 7: Binary File Preservation
# **Validates: Requirements 5.4**
@given(
    file_name=st.text(
        alphabet=string.ascii_lowercase + string.digits + "_",
        min_size=1,
        max_size=10,
    ),
    binary_content=st.binary(min_size=10, max_size=500),
    var_name=var_name_strategy,
)
@settings(max_examples=100)
def test_render_does_not_substitute_variables_in_binary_files(
    file_name: str, binary_content: bytes, var_name: str
) -> None:
    """Binary files do not have variable substitution applied."""
    # Create binary content that contains what looks like a variable pattern
    # but should NOT be substituted
    pattern_bytes = f"{{{{{var_name}}}}}".encode("utf-8")
    binary_with_pattern = binary_content + b"\x00" + pattern_bytes

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        template_dir = tmp_path / "templates"
        output_dir = tmp_path / "output"
        template_dir.mkdir()

        # Create a binary file with variable-like pattern
        binary_file = template_dir / f"{file_name}.bin"
        binary_file.write_bytes(binary_with_pattern)

        engine = TemplateEngine(template_dir)
        # Even though var_name is not in variables, it should not raise
        # because binary files skip substitution
        engine.render(output_dir, {})

        # Verify binary file was copied exactly (pattern not substituted)
        output_file = output_dir / f"{file_name}.bin"
        assert output_file.exists()
        assert output_file.read_bytes() == binary_with_pattern
