# SPDX-License-Identifier: MIT
"""
APWorld implementation for {{game}}.

This package provides Archipelago multiworld randomizer support for {{game}}.
When loaded by Archipelago, it registers the {{class_name}}World class which
defines all items, locations, and game logic.

Package Structure:
    world.py - Main World class implementation

For development and testing:
    - Run `apworld build` to create a distributable .apworld file
    - Run `pytest` to execute the test suite

See Also:
    https://archipelago.gg/ - Archipelago project homepage
    https://github.com/ArchipelagoMW/Archipelago - Main repository
"""

from .world import {{class_name}}World

__all__ = ["{{class_name}}World"]
