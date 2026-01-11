# SPDX-License-Identifier: MIT
"""Sample World implementation."""


# Stub base class for testing - in real Archipelago this would be imported
class World:
    """Base class stub for testing."""

    pass


class SampleWorld(World):
    """A sample world for testing."""

    game = "Sample Game"

    def __init__(self):
        self.items = []
        self.locations = []
