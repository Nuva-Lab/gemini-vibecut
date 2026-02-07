"""
World model - represents a story setting created from user photos.

A world is a place where stories happen. It's extracted from photos
the user has taken or saved (manga exhibits, game screenshots, landscapes).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime
import uuid


@dataclass
class World:
    """
    A story world/setting created from a user's photo.

    Worlds provide the backdrop for character stories.
    They carry mood, visual style, and narrative potential.
    """

    # Identity
    name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Source
    source_image: Optional[Path] = None

    # Understanding (from Gemini 3)
    analysis: dict = field(default_factory=dict)
    # analysis = {
    #     "setting_type": "cyberpunk city",
    #     "visual_style": {...},
    #     "atmosphere": "mysterious",
    #     "mood_keywords": [...],
    #     "story_potential": [...]
    # }

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    times_used: int = 0

    @property
    def setting_type(self) -> str:
        """Get the type of setting."""
        return self.analysis.get("setting_type", "unknown")

    @property
    def atmosphere(self) -> str:
        """Get the atmosphere/mood."""
        return self.analysis.get("atmosphere", "mysterious")

    @property
    def visual_style(self) -> dict:
        """Get visual style information."""
        return self.analysis.get("visual_style", {})

    @property
    def mood_keywords(self) -> list:
        """Get mood keywords for music generation."""
        return self.analysis.get("mood_keywords", [])

    def to_prompt_context(self) -> str:
        """Generate context string for use in prompts."""
        style = self.visual_style
        return f"""
World: {self.name}
Setting: {self.setting_type}
Atmosphere: {self.atmosphere}
Color Palette: {style.get('color_palette', 'varied')}
Lighting: {style.get('lighting', 'natural')}
Visual Style: {style.get('evoked_style', 'anime')}
Mood: {', '.join(self.mood_keywords)}
"""

    def to_dict(self) -> dict:
        """Serialize world to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "source_image": str(self.source_image) if self.source_image else None,
            "analysis": self.analysis,
            "created_at": self.created_at.isoformat(),
            "times_used": self.times_used,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "World":
        """Deserialize world from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data["name"],
            source_image=Path(data["source_image"]) if data.get("source_image") else None,
            analysis=data.get("analysis", {}),
            times_used=data.get("times_used", 0),
        )
