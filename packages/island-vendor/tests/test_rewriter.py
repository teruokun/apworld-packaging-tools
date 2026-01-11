# SPDX-License-Identifier: MIT
"""Tests for the import rewriter module."""

import pytest

from island_vendor.config import CORE_AP_MODULES, VendorConfig
from island_vendor.rewriter import (
    ImportRewriteError,
    ImportRewriter,
    RewriteResult,
    rewrite_source,
)


class TestRewriteSource:
    """Tests for rewrite_source function."""

    def test_simple_import_rewrite(self):
        """Simple import should be rewritten."""
        source = "import yaml"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from my_game._vendor import yaml" in result
        assert rewritten == 1
        assert preserved == 0

    def test_from_import_rewrite(self):
        """From import should be rewritten."""
        source = "from yaml import safe_load"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from my_game._vendor.yaml import safe_load" in result
        assert rewritten == 1

    def test_dotted_from_import_rewrite(self):
        """Dotted from import should be rewritten."""
        source = "from yaml.parser import Parser"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from my_game._vendor.yaml.parser import Parser" in result
        assert rewritten == 1

    def test_core_ap_import_preserved(self):
        """Core AP imports should be preserved."""
        source = "from BaseClasses import Item, Location"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from BaseClasses import Item, Location" in result
        assert rewritten == 0
        assert preserved == 1

    def test_worlds_import_preserved(self):
        """Worlds imports should be preserved."""
        source = "from worlds.generic.Rules import set_rule"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from worlds.generic.Rules import set_rule" in result
        assert preserved == 1

    def test_options_import_preserved(self):
        """Options imports should be preserved."""
        source = "from Options import Toggle, Choice"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from Options import Toggle, Choice" in result
        assert preserved == 1

    def test_mixed_imports(self):
        """Mixed imports should be handled correctly."""
        source = """import yaml
from BaseClasses import Item
from yaml import safe_load
from Options import Toggle"""
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from my_game._vendor import yaml" in result
        assert "from BaseClasses import Item" in result
        assert "from my_game._vendor.yaml import safe_load" in result
        assert "from Options import Toggle" in result
        assert rewritten == 2
        assert preserved == 2

    def test_import_with_alias(self):
        """Import with alias should preserve alias."""
        source = "import yaml as y"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from my_game._vendor import yaml as y" in result

    def test_from_import_with_alias(self):
        """From import with alias should preserve alias."""
        source = "from yaml import safe_load as load"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from my_game._vendor.yaml import safe_load as load" in result

    def test_relative_import_preserved(self):
        """Relative imports should be preserved."""
        source = "from . import utils\nfrom ..common import helper"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from . import utils" in result
        assert "from ..common import helper" in result
        assert preserved == 2

    def test_non_vendored_import_preserved(self):
        """Non-vendored imports should be preserved."""
        source = "import os\nimport sys"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "import os" in result
        assert "import sys" in result
        assert rewritten == 0
        assert preserved == 2

    def test_multiple_vendored_packages(self):
        """Multiple vendored packages should all be rewritten."""
        source = """import yaml
import requests
from pydantic import BaseModel"""
        vendored = {"yaml", "requests", "pydantic"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "from my_game._vendor import yaml" in result
        assert "from my_game._vendor import requests" in result
        assert "from my_game._vendor.pydantic import BaseModel" in result
        assert rewritten == 3

    def test_syntax_error_raises_exception(self):
        """Syntax error in source should raise ImportRewriteError."""
        source = "import yaml\ndef broken("
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        with pytest.raises(ImportRewriteError, match="Syntax error"):
            rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

    def test_empty_source(self):
        """Empty source should return empty result."""
        source = ""
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert result == ""
        assert rewritten == 0
        assert preserved == 0

    def test_source_with_no_imports(self):
        """Source with no imports should be unchanged."""
        source = "x = 1\ny = 2"
        vendored = {"yaml"}
        namespace = "my_game._vendor"

        result, rewritten, preserved = rewrite_source(source, vendored, namespace, CORE_AP_MODULES)

        assert "x = 1" in result
        assert "y = 2" in result
        assert rewritten == 0
        assert preserved == 0


class TestImportRewriter:
    """Tests for ImportRewriter class."""

    def test_rewriter_tracks_counts(self):
        """Rewriter should track rewritten and preserved counts."""
        rewriter = ImportRewriter(
            vendored_modules={"yaml"},
            vendor_namespace="my_game._vendor",
            core_ap_modules=CORE_AP_MODULES,
        )
        assert rewriter.imports_rewritten == 0
        assert rewriter.imports_preserved == 0


class TestRewriteResult:
    """Tests for RewriteResult dataclass."""

    def test_result_fields(self):
        """RewriteResult should have expected fields."""
        from pathlib import Path

        result = RewriteResult(
            source_path=Path("src/game.py"),
            output_path=Path("build/game.py"),
            imports_rewritten=5,
            imports_preserved=3,
            modified=True,
        )
        assert result.source_path == Path("src/game.py")
        assert result.output_path == Path("build/game.py")
        assert result.imports_rewritten == 5
        assert result.imports_preserved == 3
        assert result.modified is True

    def test_default_values(self):
        """RewriteResult should have sensible defaults."""
        from pathlib import Path

        result = RewriteResult(
            source_path=Path("src/game.py"),
            output_path=Path("build/game.py"),
        )
        assert result.imports_rewritten == 0
        assert result.imports_preserved == 0
        assert result.modified is False


class TestRewriteWithVendorConfig:
    """Tests using VendorConfig for rewriting."""

    def test_rewrite_with_config(self):
        """Rewriting with VendorConfig should work."""
        config = VendorConfig(package_name="my_game")
        source = "import yaml\nfrom BaseClasses import Item"
        vendored = {"yaml"}

        result, rewritten, preserved = rewrite_source(
            source, vendored, config.vendor_namespace, config.core_ap_modules
        )

        assert "from my_game._vendor import yaml" in result
        assert "from BaseClasses import Item" in result
        assert rewritten == 1
        assert preserved == 1

    def test_rewrite_with_custom_namespace(self):
        """Rewriting with custom namespace should work."""
        config = VendorConfig(package_name="my_game", namespace="_deps")
        source = "import yaml"
        vendored = {"yaml"}

        result, rewritten, preserved = rewrite_source(
            source, vendored, config.vendor_namespace, config.core_ap_modules
        )

        assert "from my_game._deps import yaml" in result
