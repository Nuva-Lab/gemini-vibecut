"""
Character model - represents an anime character created from user assets.

A character is the transformation of a personal photo (pet or person)
into a reusable anime character with personality and visual consistency.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime
import uuid


@dataclass
class Character:
    """
    An anime character created from a user's photo.

    Characters are the core reusable asset in the creative universe.
    Once created, they can appear in any scene, world, or story.
    """

    # Identity
    name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    persona: str = ""  # User-provided one-line persona

    # Source
    source_image: Optional[Path] = None  # Single reference (backwards compat)
    source_images: list[Path] = field(default_factory=list)  # Multiple references
    source_type: Literal["pet", "person", "sketch", "description"] = "pet"

    # Understanding (from Gemini 3)
    analysis: dict = field(default_factory=dict)
    concept: dict = field(default_factory=dict)

    # Generation
    style: str = "anime"
    generated_images: dict = field(default_factory=dict)
    # generated_images = {
    #     "full_body": Path,
    #     "portrait": Path,
    #     "expressions": [Path, ...],
    # }

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    times_used: int = 0

    def __post_init__(self):
        """Validate character on creation."""
        if not self.name:
            raise ValueError("Character must have a name")

    @property
    def personality_summary(self) -> str:
        """Get a short personality summary for prompts."""
        return self.concept.get("personality_summary", "A mysterious character")

    @property
    def visual_description(self) -> str:
        """Get visual description for generation prompts."""
        return self.concept.get("visual_description", self.name)

    @property
    def archetype(self) -> str:
        """Get character archetype."""
        return self.concept.get("character_archetype", "protagonist")

    def to_prompt_context(self) -> str:
        """Generate context string for use in prompts."""
        persona_line = f"Persona: {self.persona}\n" if self.persona else ""
        return f"""
Character: {self.name}
{persona_line}Archetype: {self.archetype}
Visual: {self.visual_description}
Personality: {self.personality_summary}
Style: {self.style}
"""

    def to_dict(self) -> dict:
        """Serialize character to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type,
            "source_image": str(self.source_image) if self.source_image else None,
            "source_images": [str(p) for p in self.source_images],
            "analysis": self.analysis,
            "concept": self.concept,
            "style": self.style,
            "created_at": self.created_at.isoformat(),
            "times_used": self.times_used,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        """Deserialize character from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data["name"],
            source_type=data.get("source_type", "pet"),
            source_image=Path(data["source_image"]) if data.get("source_image") else None,
            source_images=[Path(p) for p in data.get("source_images", [])],
            analysis=data.get("analysis", {}),
            concept=data.get("concept", {}),
            style=data.get("style", "anime"),
            times_used=data.get("times_used", 0),
        )
