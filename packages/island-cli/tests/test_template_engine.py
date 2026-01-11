# SPDX-License-Identifier: MIT
"""Tests for the template engine."""

from __future__ import annotations

import string
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from island_cli.template_engine import TemplateEngine, TemplateError


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
    """For any variables dict, substitution replaces all {{variable}} patterns."""
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
    """For any undefined variable, substitution raises TemplateError."""
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
