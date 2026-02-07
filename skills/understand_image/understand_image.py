"""
Image Understanding Skill - Gemini 3 multimodal analysis.

This skill uses Gemini 3 Flash to understand:
- Pet photos → features, personality, character potential
- Person photos → style, aesthetic, anime traits
- World photos → setting, mood, visual style
"""

import json
import logging
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types

from config import GOOGLE_API_KEY, GEMINI_MODEL, TEMPERATURE_UNDERSTANDING
from agent.prompts import Prompts

logger = logging.getLogger(__name__)


class ImageUnderstanding:
    """
    Gemini 3 powered image understanding.

    This is the foundation skill - understanding what users have
    before we can help them create something new.
    """

    def __init__(self, client: genai.Client = None):
        """Initialize with Gemini client."""
        self.client = client or genai.Client(api_key=GOOGLE_API_KEY)
        self.model = GEMINI_MODEL

    async def analyze(
        self,
        image_path: Path,
        analysis_type: Literal["pet", "person", "world"],
    ) -> dict:
        """
        Analyze an image based on its type.

        Args:
            image_path: Path to the image file
            analysis_type: What kind of analysis to perform

        Returns:
            Structured analysis as dictionary
        """
        # Select prompt based on analysis type
        prompts = {
            "pet": Prompts.ANALYZE_PET_PHOTO,
            "person": Prompts.ANALYZE_PERSON_PHOTO,
            "world": Prompts.ANALYZE_WORLD_PHOTO,
        }
        prompt = prompts[analysis_type]

        # Load image
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Determine mime type
        suffix = image_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        mime_type = mime_types.get(suffix, "image/jpeg")

        logger.info(f"Analyzing {analysis_type} image: {image_path.name}")

        # Call Gemini
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=image_data, mime_type=mime_type),
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=TEMPERATURE_UNDERSTANDING,
                response_mime_type="application/json",
            ),
        )

        # Parse response
        try:
            analysis = json.loads(response.text)
            logger.info(f"Analysis complete for {image_path.name}")
            return analysis
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse analysis response: {e}")
            logger.error(f"Raw response: {response.text}")
            raise

    async def analyze_pet(self, image_path: Path) -> dict:
        """Convenience method for pet analysis."""
        return await self.analyze(image_path, "pet")

    async def analyze_person(self, image_path: Path) -> dict:
        """Convenience method for person analysis."""
        return await self.analyze(image_path, "person")

    async def analyze_world(self, image_path: Path) -> dict:
        """Convenience method for world analysis."""
        return await self.analyze(image_path, "world")

    async def detect_image_type(self, image_path: Path) -> str:
        """
        Auto-detect what type of image this is.

        Returns: "pet", "person", "world", or "unknown"
        """
        with open(image_path, "rb") as f:
            image_data = f.read()

        prompt = """
Analyze this image and determine its primary subject type.

Respond with exactly one of:
- "pet" - if it's primarily a photo of a pet animal (dog, cat, etc.)
- "person" - if it's primarily a photo of a person/people
- "world" - if it's primarily a landscape, scene, interior, or environment
- "unknown" - if you can't determine

Respond with just the single word, nothing else.
"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=1,
            ),
        )

        result = response.text.strip().lower()
        if result in ["pet", "person", "world"]:
            return result
        return "unknown"
