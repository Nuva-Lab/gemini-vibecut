"""
Project model - represents a user's creative universe.

A project is the container for all characters, worlds, and creations.
It grows over time as users add more assets and create more content.
This is where compound value lives.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime
import json
import uuid

from .character import Character
from .world import World


@dataclass
class Creation:
    """A single creative output (video, image, etc.)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    type: str = "video"  # video, image, music
    output_path: Optional[Path] = None
    characters_used: list[str] = field(default_factory=list)  # character IDs
    world_used: Optional[str] = None  # world ID
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "output_path": str(self.output_path) if self.output_path else None,
            "characters_used": self.characters_used,
            "world_used": self.world_used,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Project:
    """
    A user's creative universe - the container for compound value.

    The project grows over time:
    - Characters accumulate and can be reused
    - Worlds become familiar settings
    - Creations reference past assets
    - The whole becomes greater than the parts
    """

    # Identity
    name: str = "My Creative Universe"
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Assets
    characters: dict[str, Character] = field(default_factory=dict)
    worlds: dict[str, World] = field(default_factory=dict)
    creations: list[Creation] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_modified: datetime = field(default_factory=datetime.now)

    # =========================================================================
    # Character Management
    # =========================================================================

    def add_character(self, character: Character) -> None:
        """Add a character to the project."""
        self.characters[character.id] = character
        self.last_modified = datetime.now()

    def get_character(self, character_id: str) -> Optional[Character]:
        """Get a character by ID."""
        return self.characters.get(character_id)

    def list_characters(self) -> list[Character]:
        """List all characters in the project."""
        return list(self.characters.values())

    # =========================================================================
    # World Management
    # =========================================================================

    def add_world(self, world: World) -> None:
        """Add a world to the project."""
        self.worlds[world.id] = world
        self.last_modified = datetime.now()

    def get_world(self, world_id: str) -> Optional[World]:
        """Get a world by ID."""
        return self.worlds.get(world_id)

    def list_worlds(self) -> list[World]:
        """List all worlds in the project."""
        return list(self.worlds.values())

    # =========================================================================
    # Creation Management
    # =========================================================================

    def add_creation(self, creation: Creation) -> None:
        """Add a creation to the project."""
        self.creations.append(creation)
        self.last_modified = datetime.now()

        # Update usage counts
        for char_id in creation.characters_used:
            if char := self.characters.get(char_id):
                char.times_used += 1

        if creation.world_used:
            if world := self.worlds.get(creation.world_used):
                world.times_used += 1

    # =========================================================================
    # Persistence
    # =========================================================================

    def save(self, path: Path) -> None:
        """Save project to JSON file."""
        data = {
            "id": self.id,
            "name": self.name,
            "characters": {k: v.to_dict() for k, v in self.characters.items()},
            "worlds": {k: v.to_dict() for k, v in self.worlds.items()},
            "creations": [c.to_dict() for c in self.creations],
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "Project":
        """Load project from JSON file."""
        with open(path) as f:
            data = json.load(f)

        project = cls(
            id=data["id"],
            name=data["name"],
        )

        # Load characters
        for char_data in data.get("characters", {}).values():
            project.characters[char_data["id"]] = Character.from_dict(char_data)

        # Load worlds
        for world_data in data.get("worlds", {}).values():
            project.worlds[world_data["id"]] = World.from_dict(world_data)

        return project

    # =========================================================================
    # Summary
    # =========================================================================

    def summary(self) -> str:
        """Get a summary of the project."""
        return f"""
Project: {self.name}
Characters: {len(self.characters)}
Worlds: {len(self.worlds)}
Creations: {len(self.creations)}
Last Modified: {self.last_modified.strftime('%Y-%m-%d %H:%M')}
"""
