# SPDX-License-Identifier: MIT
"""Tests for {{game}} world implementation."""

from test.bases import WorldTestBase


class {{class_name}}TestBase(WorldTestBase):
    """Base test class for {{game}}."""

    game = "{{game}}"


class Test{{class_name}}World({{class_name}}TestBase):
    """Test cases for {{game}} world."""

    def test_world_setup(self) -> None:
        """Test that the world initializes correctly."""
        self.assertEqual(self.world.game, "{{game}}")
