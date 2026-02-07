"""
Data models for the Creative Universe.

These models represent the building blocks of a user's creative universe:
- Characters (pets, people → anime characters)
- Worlds (photos → story settings)
- Projects (collections of characters, worlds, and creations)
"""

from .character import Character
from .world import World
from .project import Project

__all__ = ["Character", "World", "Project"]
