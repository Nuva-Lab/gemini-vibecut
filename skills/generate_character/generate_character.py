"""
Character Generation Skill - Nano Banana Pro image generation.

This skill generates anime character images from analysis and concepts
using Gemini 3 Pro Image (Nano Banana Pro) with:
- 2K resolution output
- Reference image support for character consistency
- Interleaved multi-image generation (full body + portrait in one call)
"""

import logging
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image

from config import (
    GOOGLE_API_KEY,
    NANO_BANANA_MODEL,
    NANO_BANANA_RESOLUTION,
    OUTPUT_DIR,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)
from models.character import Character

logger = logging.getLogger(__name__)


class CharacterGenerator:
    """
    Generate anime character images using Nano Banana Pro.

    Takes a Character object (with analysis and concept) and
    generates visual representations using reference-guided generation.

    Key features:
    - Uses source photo as reference for consistency
    - Generates multiple variants in a single API call
    - Handles interleaved text + image responses
    """

    def __init__(self, client: genai.Client = None):
        """Initialize with Gemini client."""
        self.client = client or genai.Client(api_key=GOOGLE_API_KEY)
        self.model = NANO_BANANA_MODEL
        self.resolution = NANO_BANANA_RESOLUTION
        self.output_dir = OUTPUT_DIR / "characters"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_character_sheet(
        self,
        character: Character,
    ) -> dict[str, Path]:
        """
        Generate full character sheet (multiple views) in ONE API call.

        Uses Nano Banana Pro's interleaved output capability to generate
        both full_body and portrait images in a single request.

        Args:
            character: Character object with analysis/concept populated

        Returns:
            Dict mapping variant names to file paths:
            {
                "full_body": Path("..."),
                "portrait": Path("...")
            }
        """
        # Load reference images (support both multi and single)
        reference_images = []

        # Prefer source_images (multi-reference) over source_image (single)
        if character.source_images:
            for img_path in character.source_images:
                if img_path.exists():
                    reference_images.append(Image.open(img_path))
                    logger.info(f"Loaded reference: {img_path}")
        elif character.source_image and character.source_image.exists():
            reference_images.append(Image.open(character.source_image))
            logger.info(f"Loaded single reference: {character.source_image}")

        # Build the generation prompt
        prompt = self._build_character_sheet_prompt(character)

        # Build contents list (all reference images first, then prompt)
        contents = reference_images + [prompt]

        logger.info(f"Generating character sheet for: {character.name}")
        logger.info(f"Using model: {self.model}, resolution: {self.resolution}")

        # Generate with retry logic
        response = await self._generate_with_retry(contents)

        if response is None:
            logger.error("Failed to generate character sheet after retries")
            return {}

        # Process interleaved response (text + multiple images)
        results = self._process_interleaved_response(response, character)

        # Store in character object
        character.generated_images = results

        logger.info(f"Generated {len(results)} images for {character.name}")
        return results

    async def generate_character_image(
        self,
        character: Character,
        variant: str = "full_body",
    ) -> Optional[Path]:
        """
        Generate a single character image variant.

        For cases where you only need one specific view.

        Args:
            character: Character object with analysis/concept
            variant: Type of image ("full_body", "portrait", "expression")

        Returns:
            Path to generated image, or None if generation failed
        """
        reference_image = None
        if character.source_image and character.source_image.exists():
            reference_image = Image.open(character.source_image)

        prompt = self._build_single_variant_prompt(character, variant)

        contents = []
        if reference_image:
            contents.append(reference_image)
        contents.append(prompt)

        logger.info(f"Generating {variant} for character: {character.name}")

        response = await self._generate_with_retry(contents)

        if response is None:
            return None

        # Extract single image from response
        for part in response.parts:
            if hasattr(part, 'inline_data') and part.inline_data is not None:
                try:
                    image = part.as_image()
                    output_path = self.output_dir / f"{character.id}_{variant}.png"
                    image.save(str(output_path))
                    logger.info(f"Saved {variant}: {output_path}")

                    # Update character's generated_images
                    if character.generated_images is None:
                        character.generated_images = {}
                    character.generated_images[variant] = output_path

                    return output_path
                except Exception as e:
                    logger.error(f"Failed to save image: {e}")

        return None

    def _build_character_sheet_prompt(self, character: Character) -> str:
        """Build prompt for single-image character sheet with expression variety."""
        # Extract key features from analysis
        analysis = character.analysis or {}
        concept = character.concept or {}

        physical_features = analysis.get("physical_features", {})
        personality_traits = analysis.get("personality_traits", [])

        # Build feature list from analysis
        features = []
        if physical_features.get("coat_color"):
            features.append(f"coat color: {physical_features['coat_color']}")
        if physical_features.get("coat_pattern"):
            features.append(f"pattern: {physical_features['coat_pattern']}")
        if physical_features.get("eye_color"):
            features.append(f"eye color: {physical_features['eye_color']}")
        if physical_features.get("distinctive_features"):
            features.extend(physical_features["distinctive_features"])

        features_text = ", ".join(features) if features else "distinctive features from the reference"
        personality_text = ", ".join(personality_traits[:3]) if personality_traits else "friendly and expressive"

        # Determine number of reference images
        num_refs = len(character.source_images) if character.source_images else (1 if character.source_image else 0)
        ref_intro = f"Using the {num_refs} attached reference photo{'s' if num_refs > 1 else ''}" if num_refs > 0 else "Based on the description"
        multi_ref_note = "\n\nIMPORTANT: These photos all show the SAME subject. Identify the consistent character across all images and create ONE character sheet for that single subject only." if num_refs > 1 else ""

        prompt = f"""{ref_intro}, create an anime character reference sheet in VERTICAL format.{multi_ref_note}

Character: {character.name}
{character.to_prompt_context()}

Key Features to Preserve: {features_text}
Personality: {personality_text}

Create a CHARACTER REFERENCE SHEET showing this character in multiple views and expressions.

INCLUDE ON THE SHEET:
- One prominent FULL BODY view (head to feet, natural standing or sitting pose)
- 2-3 different EXPRESSIONS showing personality (happy, curious, sleepy, playful, etc.)
- 1-2 ACTION POSES or alternate angles (stretching, running, lounging, looking back, etc.)

LAYOUT:
- Arrange views naturally on the sheet — no rigid grid required
- Main full body should be the largest/most prominent
- Smaller expression heads and action poses can be arranged around it
- Clean soft background that doesn't distract

STYLE:
- {character.style} anime style with clean cel-shaded lines
- Vibrant colors matching the reference
- Consistent character design across ALL views
- Expressive, appealing, full of personality

This reference sheet will be used for video keyframes and storytelling — clarity and consistency are essential.

Generate the character reference sheet now."""

        return prompt

    def _build_single_variant_prompt(self, character: Character, variant: str) -> str:
        """Build prompt for a single image variant."""
        variant_specs = {
            "full_body": "Full body standing pose, 3/4 angle, complete body visible, clean gradient background.",
            "portrait": "Close-up portrait, head and shoulders, facing 3/4 view, expressive eyes, warm expression.",
            "expression": "Expression sheet grid showing: happy, sad, surprised, determined. Four expressions in a 2x2 grid.",
            "action": "Dynamic action pose showing movement, energy lines, dramatic angle.",
        }

        variant_desc = variant_specs.get(variant, variant_specs["full_body"])

        prompt = f"""Using the attached reference photo, create an anime character image.

Character: {character.name}
{character.to_prompt_context()}

Image Type: {variant.replace('_', ' ').title()}
{variant_desc}

Style: {character.style} anime
- Clean cel-shaded linework
- Suitable for animation
- Capture distinctive features from reference

Generate the image now."""

        return prompt

    async def _generate_with_retry(
        self,
        contents: list,
        max_retries: int = None,
    ):
        """Generate content with exponential backoff retry."""
        max_retries = max_retries or MAX_RETRIES

        config = types.GenerateContentConfig(
            response_modalities=['TEXT', 'IMAGE'],
            image_config=types.ImageConfig(
                aspect_ratio="9:16",  # Tall vertical for character sheet (full body + expressions + poses)
                image_size=self.resolution
            )
        )

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config
                )
                return response

            except Exception as e:
                error_msg = str(e).lower()

                # Check for rate limit / quota errors
                if "resource exhausted" in error_msg or "quota" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)
                        logger.warning(f"Rate limited, waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Rate limit exceeded after {max_retries} retries")
                        raise

                # Log and re-raise other errors
                logger.error(f"Generation error: {e}")
                raise

        return None

    def _process_interleaved_response(
        self,
        response,
        character: Character,
    ) -> dict[str, Path]:
        """
        Process interleaved response with text and multiple images.

        Nano Banana Pro returns responses with text and images woven together.
        This method extracts and saves each image in sequence.
        """
        results = {}
        image_index = 0
        variant_names = ["full_body", "portrait"]

        for part in response.parts:
            # Handle text parts (model commentary)
            if hasattr(part, 'text') and part.text:
                logger.debug(f"Model response: {part.text}")

            # Handle image parts
            elif hasattr(part, 'inline_data') and part.inline_data is not None:
                # Skip thought images if present
                if hasattr(part, 'thought') and part.thought:
                    logger.debug("Skipping thought image")
                    continue

                try:
                    image = part.as_image()

                    if image_index < len(variant_names):
                        variant = variant_names[image_index]
                    else:
                        variant = f"extra_{image_index}"

                    output_path = self.output_dir / f"{character.id}_{variant}.png"
                    image.save(str(output_path))
                    results[variant] = output_path
                    logger.info(f"Saved {variant}: {output_path}")
                    image_index += 1

                except Exception as e:
                    logger.error(f"Failed to process image part: {e}")

        return results
