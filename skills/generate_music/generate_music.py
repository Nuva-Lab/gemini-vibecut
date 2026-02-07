"""
Music Generation Skill - Google Music Generation API.

This skill generates original background music for videos.
https://ai.google.dev/gemini-api/docs/music-generation
"""

import logging
from pathlib import Path
from typing import Optional

from google import genai

from config import (
    GOOGLE_API_KEY,
    OUTPUT_DIR,
    MUSIC_DURATION_SECONDS,
    MUSIC_STYLES,
)
from agent.prompts import Prompts

logger = logging.getLogger(__name__)


class MusicGenerator:
    """
    Generate original background music using Google's Music Generation API.

    Creates music that matches the mood and pacing of video scenes.
    """

    def __init__(self, client: genai.Client = None):
        """Initialize with Gemini client."""
        self.client = client or genai.Client(api_key=GOOGLE_API_KEY)
        self.output_dir = OUTPUT_DIR / "music"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_bgm(
        self,
        scene_description: str,
        mood: str,
        duration: int = MUSIC_DURATION_SECONDS,
        style: Optional[str] = None,
    ) -> Path:
        """
        Generate background music for a scene.

        Args:
            scene_description: What's happening in the scene
            mood: The emotional tone (adventurous, melancholic, etc.)
            duration: Duration in seconds
            style: Optional music style preference

        Returns:
            Path to generated audio file
        """
        # Build music prompt
        prompt = Prompts.GENERATE_MUSIC_PROMPT.format(
            scene_description=scene_description,
            mood=mood,
            duration=duration,
            music_style=style or "anime_orchestral",
        )

        logger.info(f"Generating music: {mood}, {duration}s")

        # TODO: Implement actual Music Generation API call
        # Reference: https://ai.google.dev/gemini-api/docs/music-generation
        #
        # response = self.client.models.generate_music(
        #     prompt=prompt,
        #     config=types.GenerateMusicConfig(
        #         duration_seconds=duration,
        #     ),
        # )
        #
        # output_path = self.output_dir / f"bgm_{mood}_{duration}s.mp3"
        # with open(output_path, "wb") as f:
        #     f.write(response.audio.data)

        output_path = self.output_dir / f"bgm_{mood.replace(' ', '_')}_{duration}s.mp3"
        logger.info(f"Music would be saved to: {output_path}")

        return output_path

    async def generate_for_scene(
        self,
        scene_concept: dict,
        duration: int = MUSIC_DURATION_SECONDS,
    ) -> Path:
        """
        Generate music based on a scene concept.

        Extracts mood and style from the scene concept.
        """
        mood = scene_concept.get("mood_for_music", "adventurous")
        scene_desc = scene_concept.get("scene_description", "")
        emotional_arc = scene_concept.get("emotional_arc", "")

        description = f"{scene_desc}. Emotional arc: {emotional_arc}"

        return await self.generate_bgm(
            scene_description=description,
            mood=mood,
            duration=duration,
        )

    def get_available_styles(self) -> list[str]:
        """Return list of available music styles."""
        return MUSIC_STYLES
