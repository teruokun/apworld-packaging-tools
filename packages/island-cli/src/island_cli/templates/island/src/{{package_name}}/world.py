# SPDX-License-Identifier: MIT
"""
World implementation for {{game}}.

This module defines the core World class that integrates {{game}} with Archipelago's
randomizer framework. The World class is responsible for:

- Defining items and locations available in the game
- Creating the game's region graph and access rules
- Generating randomized game data

For more information on implementing Island packages, see:
- https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/world%20api.md
- https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/adding%20games.md
"""

from typing import ClassVar

from BaseClasses import Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import WebWorld, World


class {{class_name}}WebWorld(WebWorld):
    """
    Web configuration for {{game}}.

    This class configures how {{game}} appears on the Archipelago website,
    including the visual theme, tutorials, and option groups.

    Attributes:
        theme: Visual theme for the game's web pages. Options include:
               'grass', 'dirt', 'grassFlowers', 'ice', 'jungle',
               'ocean', 'partyTime', 'stone'
        tutorials: List of Tutorial objects linking to setup guides

    See Also:
        worlds.AutoWorld.WebWorld for all available configuration options
    """

    theme = "grass"
    tutorials = [
        Tutorial(
            tutorial_name="Setup Guide",
            description="A guide to setting up {{game}} for Archipelago.",
            language="English",
            file_name="setup_en.md",
            link="setup/en",
            authors=["{{author}}"],
        )
    ]


class {{class_name}}World(World):
    """
    World implementation for {{game}}.

    This class defines all items, locations, and game logic for {{game}}.
    It inherits from worlds.AutoWorld.World and must implement several
    required attributes and methods.

    Required Class Attributes:
        game: Display name of the game (shown in Archipelago UI)
        item_name_to_id: Mapping of item names to unique integer IDs
        location_name_to_id: Mapping of location names to unique integer IDs

    Key Methods to Implement:
        create_item(): Create an Item instance by name
        create_regions(): Build the game's region graph
        create_items(): Populate the item pool
        set_rules(): Define access rules for locations

    See Also:
        worlds.AutoWorld.World for the complete API documentation
        BaseClasses.Item, BaseClasses.Location, BaseClasses.Region
    """

    game = "{{game}}"
    web = {{class_name}}WebWorld()

    # ==========================================================================
    # Item and Location ID Mappings
    # ==========================================================================
    #
    # These dictionaries map human-readable names to unique integer IDs.
    # IDs must be unique across ALL Archipelago games, so use a base offset.
    #
    # Recommended ID ranges:
    # - Request an official range from the Archipelago team for published worlds
    # - For development, use a high base like 0xABC00000 to avoid conflicts
    #
    # ID 0 (None) is reserved for events (locations/items that don't get sent
    # over the network). Events are useful for tracking game state.
    #
    # TODO: Replace these example entries with your game's actual items/locations
    # ==========================================================================

    # Base ID offset - replace with your assigned range for published worlds
    _BASE_ID: ClassVar[int] = 0xABC00000

    item_name_to_id: ClassVar[dict[str, int]] = {
        # Example progression item - required to complete the game
        "Example Key": _BASE_ID + 1,
        # Example useful item - helpful but not required
        "Example Upgrade": _BASE_ID + 2,
        # Example filler item - basic collectible
        "Example Coin": _BASE_ID + 3,
        # TODO: Add your game's items here
    }

    location_name_to_id: ClassVar[dict[str, int]] = {
        # Example location - where items can be placed
        "Example Chest 1": _BASE_ID + 100,
        "Example Chest 2": _BASE_ID + 101,
        "Boss Reward": _BASE_ID + 102,
        # TODO: Add your game's locations here
    }

    def create_item(self, name: str) -> Item:
        """
        Create an Item instance for this world.

        This method is called by the Archipelago framework when it needs to
        create items for the item pool or for placement.

        Args:
            name: The name of the item to create. Must be a key in item_name_to_id.

        Returns:
            An Item instance with the appropriate classification.

        Note:
            Item classifications affect how the randomizer places items:
            - progression: Required to complete the game
            - useful: Helpful but not required
            - filler: Basic items to fill remaining locations
            - trap: Items with negative effects

        Example:
            >>> world.create_item("Example Key")
            Item('Example Key', ItemClassification.progression, ...)
        """
        item_id = self.item_name_to_id.get(name)

        # TODO: Implement proper classification logic for your items
        # This example treats all items as progression - adjust as needed
        classification = ItemClassification.progression

        return Item(
            name,
            classification,
            item_id,
            self.player,
        )

    def create_regions(self) -> None:
        """
        Create and connect regions for this world.

        Regions represent areas of the game that can contain locations.
        The region graph defines how areas connect and what items are
        needed to traverse between them.

        Every world must have at least a "Menu" region, which serves as
        the starting point for logic calculations.

        Example region structure:
            Menu -> Overworld -> Dungeon 1 -> Boss Room
                             -> Dungeon 2 -> ...

        See Also:
            BaseClasses.Region for region configuration options
            set_rules() for defining access requirements
        """
        # Create the menu region (required - starting point for logic)
        menu = Region("Menu", self.player, self.multiworld)
        self.multiworld.regions.append(menu)

        # TODO: Create your game's regions and connect them
        # Example:
        # overworld = Region("Overworld", self.player, self.multiworld)
        # menu.connect(overworld)  # Connect Menu to Overworld
        #
        # # Add locations to regions
        # overworld.locations.append(
        #     Location(self.player, "Example Chest 1",
        #              self.location_name_to_id["Example Chest 1"], overworld)
        # )

    def create_items(self) -> None:
        """
        Create and add items to the multiworld item pool.

        This method should create all items that will be randomized and
        add them to self.multiworld.itempool. The number of items should
        generally match the number of locations.

        Items can be:
        - Added to the pool: self.multiworld.itempool.append(item)
        - Pre-placed at specific locations
        - Given to the player at start via precollected items

        See Also:
            create_item() for creating individual items
            get_filler_item_name() for filling extra locations
        """
        # TODO: Create your game's items and add them to the pool
        # Example:
        # for item_name in self.item_name_to_id:
        #     item = self.create_item(item_name)
        #     self.multiworld.itempool.append(item)
        pass

    def set_rules(self) -> None:
        """
        Set access rules for locations and region connections.

        Rules define what items are required to access locations or
        traverse between regions. The randomizer uses these rules to
        ensure the game is completable.

        Common rule patterns:
        - location.access_rule = lambda state: state.has("Item", self.player)
        - entrance.access_rule = lambda state: state.has_all(["A", "B"], self.player)
        - location.access_rule = lambda state: state.has("Key", self.player, 3)

        See Also:
            BaseClasses.CollectionState for available rule helper methods
        """
        # TODO: Define access rules for your locations
        # Example:
        # self.multiworld.get_location("Boss Reward", self.player).access_rule = \
        #     lambda state: state.has("Example Key", self.player)
        #
        # Set completion condition
        # self.multiworld.completion_condition[self.player] = \
        #     lambda state: state.has("Victory", self.player)
        pass

    def generate_basic(self) -> None:
        """
        Generate basic world structure after items and rules are set.

        This method is called after create_items() and set_rules().
        Use it for any randomization that doesn't affect logic, such as:
        - Cosmetic randomization
        - Enemy randomization
        - Text/dialogue changes

        Note:
            Use self.random for any randomization to ensure reproducibility.
        """
        pass
