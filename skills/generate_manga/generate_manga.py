"""
Manga Generation Skill - Multi-panel manga creation with Nano Banana Pro.

This skill generates sequential manga panels from a character reference
and story beats using Gemini 3 Pro Image (Nano Banana Pro) with:
- 9:16 vertical aspect ratio for each panel
- Sequential generation with previous panel as reference (visual continuity)
- Camera angle variety between panels
- Async streaming support for progressive display
"""

import asyncio
import base64
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Optional

from google import genai
from google.genai import types

from config import (
    GOOGLE_API_KEY,
    NANO_BANANA_MODEL,
    GEMINI_PRO_MODEL,
    OUTPUT_DIR,
)

logger = logging.getLogger(__name__)


@dataclass
class MangaPanel:
    """A single manga panel."""
    index: int
    story_beat: str
    dialogue: str
    image_path: Optional[Path] = None
    image_url: Optional[str] = None


@dataclass
class MangaResult:
    """Result of manga generation."""
    manga_id: str
    character_name: str
    style: str
    panels: list[MangaPanel] = field(default_factory=list)
    generation_time_seconds: float = 0.0


@dataclass
class StreamEvent:
    """Event emitted during streaming generation."""
    type: str  # 'start', 'progress', 'panel', 'panel_error', 'complete', 'error'
    data: dict = field(default_factory=dict)


# Style descriptions for image generation (video-ready keyframes)
# These should be CLEAN cinematic images, NOT manga panels
# CRITICAL: Must specify "illustrated" / "drawn" to prevent photorealistic output
STYLE_DESCRIPTIONS = {
    "manga": "ILLUSTRATED anime art style - hand-drawn appearance with clean linework, expressive anime eyes, FULL COLOR vibrant palette, cel-shaded lighting. NOT a photograph. NOT photorealistic. Must look like anime illustration.",
    "webtoon": "ILLUSTRATED Korean webtoon style - hand-drawn with soft pastel colors, clean digital illustration, emotional expressions. NOT a photograph.",
    "chibi": "ILLUSTRATED chibi/super-deformed style - hand-drawn with oversized heads, cute pastel palette, clean cartoon appearance. NOT a photograph.",
    "ghibli": "ILLUSTRATED Studio Ghibli style - hand-painted watercolor aesthetics, warm palette, detailed painted backgrounds. NOT a photograph."
}


class MangaGenerator:
    """
    Generate multi-panel manga using Nano Banana Pro.

    Takes a character reference image and story beats, generates
    sequential panels with visual continuity between them.

    Key features:
    - Sequential panel generation with image chaining
    - Camera angle parsing from story beats
    - Visual continuity instructions for consistent environment
    - Async streaming for progressive display
    """

    def __init__(self, client: genai.Client = None):
        """Initialize with Gemini client."""
        self.client = client or genai.Client(api_key=GOOGLE_API_KEY)
        self.model = NANO_BANANA_MODEL
        self.output_dir = OUTPUT_DIR / "manga"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.url_prefix = "/assets/outputs/manga"  # Overrideable for session scoping

    def _parse_camera_instruction(self, story_beat: str) -> str:
        """Parse camera direction from story beat text."""
        beat_lower = story_beat.lower()

        if "close-up" in beat_lower or "closeup" in beat_lower:
            return "CAMERA: Tight close-up shot. Fill 80% of frame with subject."
        elif "wide shot" in beat_lower or "wide-shot" in beat_lower:
            return "CAMERA: Wide establishing shot. Subject takes 30-40% of frame."
        elif "medium shot" in beat_lower:
            return "CAMERA: Medium shot from waist up. Subject takes 50-60% of frame."
        elif "low angle" in beat_lower:
            return "CAMERA: Low angle looking up at subject."
        elif "high angle" in beat_lower or "bird" in beat_lower:
            return "CAMERA: High angle looking down."
        else:
            return "CAMERA: Dynamic angle for this moment."

    async def _describe_character(self, char_name: str, char_image_part) -> str:
        """
        Use Gemini Pro to analyze a character reference sheet and produce
        a concise appearance description for embedding in panel prompts.

        This gives the image model a text anchor alongside the visual reference,
        preventing character drift on complex story beats.
        """
        prompt = f"""Analyze this character reference sheet for "{char_name}" and describe their appearance concisely.

Include ONLY visual details in 2-3 sentences:
- Hair: color, length, style
- Face: age range, facial hair, expression
- Outfit: specific clothing items and colors
- Accessories: headphones, glasses, hat, jewelry, etc.
- If this is an animal: breed, fur color, distinguishing markings

Be specific about colors and items. This description will be used to ensure the character looks the same across multiple illustrations.

Format: "{char_name} is/has..." (plain text, no bullets, no labels)"""

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=GEMINI_PRO_MODEL,
                contents=[char_image_part, types.Part.from_text(text=prompt)],
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )
            desc = response.text.strip()
            # Truncate if too long (keep prompt size reasonable)
            if len(desc) > 400:
                desc = desc[:400].rsplit('.', 1)[0] + '.'
            return desc
        except Exception as e:
            logger.warning(f"[MangaGenerator] Character description failed for {char_name}: {e}")
            return ""

    def _build_panel_prompt(
        self,
        character_names: list[str],
        story_beat: str,
        style: str,
        panel_index: int,
        total_panels: int,
        has_previous_panel: bool = False,
        char_descriptions: dict = None,
    ) -> str:
        """Build the prompt for generating a single panel with 1-2 characters."""
        camera_instruction = self._parse_camera_instruction(story_beat)
        style_desc = STYLE_DESCRIPTIONS.get(style, STYLE_DESCRIPTIONS["manga"])

        # Build character reference section with text descriptions
        descs = char_descriptions or {}

        def _char_line(idx, name):
            line = f"- [IMAGE {idx}]: {name} - Use this EXACT design for {name}"
            desc = descs.get(name, "")
            if desc:
                line += f"\n  APPEARANCE: {desc}"
            return line

        if len(character_names) == 1:
            char_ref_section = f"""CHARACTER REFERENCES:
{_char_line(1, character_names[0])}"""
        else:
            char_ref_section = f"""CHARACTER REFERENCES (2 characters in this scene):
{_char_line(1, character_names[0])}
{_char_line(2, character_names[1])}

CRITICAL: Both characters must appear as described in the story beat. Match each character to their reference image AND appearance description by name."""

        # Progression context with cinematic transitions
        if panel_index == 0:
            progression_context = """OPENING SHOT - Establish characters and setting.
TRANSITION: This is the first shot, set the scene clearly."""
        elif panel_index == total_panels - 1:
            progression_context = """FINAL SHOT - Payoff moment, emotional peak.
TRANSITION: Close on character reaction or triumphant pose."""
        elif panel_index == 1:
            progression_context = f"""Shot {panel_index + 1}/{total_panels} - Build momentum.
TRANSITION: Cut to a different angle (if previous was wide, go medium or close-up)."""
        else:
            progression_context = f"""Shot {panel_index + 1}/{total_panels} - Rising action.
TRANSITION: Camera cut - change angle significantly from previous shot."""

        # Continuity instructions when we have a previous panel
        continuity_instruction = ""
        if has_previous_panel:
            prev_image_num = len(character_names) + 1
            continuity_instruction = f"""
VISUAL CONTINUITY (MANDATORY - HIGHEST PRIORITY):
- [IMAGE {prev_image_num}] is the PREVIOUS PANEL - COPY ITS ART STYLE EXACTLY
- SAME illustration style (if previous is anime drawing, this MUST be anime drawing)
- SAME rendering technique (linework, coloring, shading method)
- SAME environment: season, time of day, lighting, background elements
- DO NOT switch between illustrated and photorealistic - stay ILLUSTRATED
- If previous panel is hand-drawn anime, this panel MUST be hand-drawn anime

CINEMATIC FLOW (for video animation):
- This panel will be animated as a separate video clip
- Think of this as a CAMERA CUT from the previous shot
- Maintain scene continuity but change camera angle
- Characters should feel like they're in the same moment/scene"""

        # Build the full prompt
        char_names_str = " and ".join(character_names)
        return f"""Generate a SINGLE clean cinematic image featuring {char_names_str}:

{char_ref_section}

ACTION: {story_beat}

{camera_instruction}

{progression_context}
{continuity_instruction}

STYLE: {style_desc}

CRITICAL REQUIREMENTS:
- ILLUSTRATED/DRAWN style - NOT photorealistic, NOT a photograph
- Each character design matches their reference image [IMAGE 1/2] AND their APPEARANCE description EXACTLY
- Characters MUST keep the same hair, clothing, accessories, and features as described above
- NEVER replace a character with a different person or animal — the SAME characters appear in EVERY panel
- CHANGE THE CAMERA ANGLE from previous panel
- Full color, vibrant, cinematic lighting
- This is a VIDEO KEYFRAME - must be clean for animation

========== ABSOLUTE RULES ==========
1. OUTPUT EXACTLY ONE (1) IMAGE - not 2, not 3, not a grid, not a sequence
2. ILLUSTRATED ANIME STYLE - hand-drawn appearance, NOT photorealistic
3. NO panel borders, NO frames, NO comic strip layouts
4. NO speed lines, NO motion blur, NO manga effects
5. NO text, NO speech bubbles, NO captions
========================================

If you generate multiple panels/frames in one image, you have FAILED.
If you generate a photorealistic image, you have FAILED.

Output: EXACTLY ONE clean, full-frame, ILLUSTRATED anime image"""

    async def generate_manga_streaming(
        self,
        character_refs: list[dict],
        story_beats: list[str],
        dialogues: list[str] = None,
        style: str = "manga",
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Generate manga panels with streaming - yields events as panels complete.

        This is the primary method for UI integration. Each panel is yielded
        as soon as it's generated, allowing progressive display.

        Args:
            character_refs: List of character references, each with 'name' and 'path' keys.
                           Maximum 2 characters supported.
            story_beats: List of story beat descriptions (one per panel)
            dialogues: Optional list of dialogue for each panel
            style: Visual style (manga, webtoon, etc.)

        Yields:
            StreamEvent objects with type and data
        """
        panel_count = len(story_beats)
        dialogues = dialogues or []
        dialogues = dialogues + [''] * (panel_count - len(dialogues))

        manga_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Validate inputs
        if panel_count < 2 or panel_count > 6:
            yield StreamEvent('error', {'message': 'Panel count must be 2-6'})
            return

        if not character_refs or len(character_refs) == 0:
            yield StreamEvent('error', {'message': 'At least 1 character required'})
            return

        if len(character_refs) > 2:
            yield StreamEvent('error', {'message': 'Maximum 2 characters per manga'})
            return

        # Load all character reference images with labels
        character_parts = []  # List of (name, image_part, label)
        character_names = []
        for idx, char_ref in enumerate(character_refs):
            char_name = char_ref['name']
            char_path = Path(char_ref['path'])

            if not char_path.exists():
                yield StreamEvent('error', {'message': f'Character image not found: {char_path}'})
                return

            try:
                with open(char_path, "rb") as f:
                    char_image_data = f.read()
                mime_type = "image/png" if char_path.suffix == ".png" else "image/jpeg"
                char_image_part = types.Part.from_bytes(data=char_image_data, mime_type=mime_type)
                character_parts.append({
                    'name': char_name,
                    'part': char_image_part,
                    'label': f"[IMAGE {idx + 1} - CHARACTER REFERENCE: {char_name}]"
                })
                character_names.append(char_name)
                logger.info(f"[MangaGenerator] Loaded character {idx + 1}: {char_name}")
            except Exception as e:
                yield StreamEvent('error', {'message': f'Failed to load character image for {char_name}: {e}'})
                return

        char_names_str = " & ".join(character_names)

        # Pre-generate text descriptions of each character using Gemini Pro
        # This gives the image model a text anchor alongside the visual reference
        char_descriptions = {}
        for char_info in character_parts:
            desc = await self._describe_character(char_info['name'], char_info['part'])
            char_descriptions[char_info['name']] = desc
            if desc:
                logger.info(f"[MangaGenerator] Character description for {char_info['name']}: {desc[:100]}...")
            else:
                logger.warning(f"[MangaGenerator] No description generated for {char_info['name']}")

        # Send start event
        yield StreamEvent('start', {
            'manga_id': manga_id,
            'total_panels': panel_count,
            'character_name': char_names_str
        })
        await asyncio.sleep(0)

        panels = []
        previous_panel_part = None

        for i, story_beat in enumerate(story_beats):
            logger.info(f"[MangaGenerator] Generating panel {i + 1}/{panel_count}: {story_beat[:50]}...")

            # Send progress event
            yield StreamEvent('progress', {
                'panel_index': i + 1,
                'total': panel_count,
                'message': f'Generating panel {i + 1}...'
            })
            await asyncio.sleep(0)

            # Build prompt with multi-character support + text descriptions
            prompt = self._build_panel_prompt(
                character_names=character_names,
                story_beat=story_beat,
                style=style,
                panel_index=i,
                total_panels=panel_count,
                has_previous_panel=(previous_panel_part is not None),
                char_descriptions=char_descriptions,
            )

            try:
                # Build content parts with clear labels:
                # [IMAGE 1]: Character 1 reference
                # [IMAGE 2]: Character 2 reference (if multi-char)
                # [IMAGE 3]: Previous panel (if exists)
                content_parts = []

                # Add all character references with labels
                for char_info in character_parts:
                    content_parts.append(types.Part.from_text(text=char_info['label']))
                    content_parts.append(char_info['part'])

                # Add previous panel reference if exists
                if previous_panel_part:
                    prev_img_num = len(character_parts) + 1
                    content_parts.append(types.Part.from_text(
                        text=f"[IMAGE {prev_img_num} - PREVIOUS PANEL: COPY THIS EXACT ART STYLE - same illustration technique, same coloring, same linework. If this is anime drawing, output anime drawing.]"
                    ))
                    content_parts.append(previous_panel_part)

                # Add the prompt
                content_parts.append(types.Part.from_text(text=prompt))

                # Run blocking Gemini call in thread
                def call_gemini():
                    return self.client.models.generate_content(
                        model=self.model,
                        contents=content_parts,
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE", "TEXT"],
                            image_config=types.ImageConfig(aspect_ratio="9:16"),
                        ),
                    )
                response = await asyncio.to_thread(call_gemini)

                # Extract image
                panel_image = None
                if response.candidates and response.candidates[0].content:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data:
                            panel_image = part.inline_data.data
                            break

                if not panel_image:
                    yield StreamEvent('panel_error', {
                        'panel_index': i + 1,
                        'message': 'Failed to generate image'
                    })
                    await asyncio.sleep(0)
                    continue

                # Decode if base64
                if isinstance(panel_image, str):
                    panel_image_bytes = base64.b64decode(panel_image)
                else:
                    panel_image_bytes = panel_image

                # Save panel
                panel_filename = f"{manga_id}_panel_{i + 1}.png"
                panel_path = self.output_dir / panel_filename
                with open(panel_path, "wb") as f:
                    f.write(panel_image_bytes)

                # Store for next iteration (image chaining)
                previous_panel_part = types.Part.from_bytes(
                    data=panel_image_bytes,
                    mime_type="image/png"
                )

                panel = MangaPanel(
                    index=i + 1,
                    story_beat=story_beat,
                    dialogue=dialogues[i],
                    image_path=panel_path,
                    image_url=f"{self.url_prefix}/{panel_filename}"
                )
                panels.append(panel)

                logger.info(f"[MangaGenerator] Panel {i + 1} saved: {panel_filename}")

                # Send panel event
                yield StreamEvent('panel', {
                    'panel_index': i + 1,
                    'total': panel_count,
                    'image_url': panel.image_url,
                    'story_beat': story_beat,
                    'dialogue': dialogues[i]
                })
                await asyncio.sleep(0)

            except Exception as e:
                logger.error(f"[MangaGenerator] Panel {i + 1} error: {e}")
                yield StreamEvent('panel_error', {
                    'panel_index': i + 1,
                    'message': str(e)[:100]
                })
                await asyncio.sleep(0)

        # Send completion event
        generation_time = time.time() - start_time
        yield StreamEvent('complete', {
            'manga_id': manga_id,
            'total_panels': len(panels),
            'generation_time': round(generation_time, 1)
        })
        await asyncio.sleep(0)

        logger.info(f"[MangaGenerator] Manga complete: {len(panels)} panels in {generation_time:.1f}s")

    async def generate_manga(
        self,
        character_refs: list[dict],
        story_beats: list[str],
        dialogues: list[str] = None,
        style: str = "manga",
    ) -> MangaResult:
        """
        Generate a complete manga (non-streaming).

        Use this when you need all panels before proceeding.
        For progressive display, use generate_manga_streaming instead.

        Args:
            character_refs: List of character references, each with 'name' and 'path' keys

        Returns:
            MangaResult with all panels
        """
        char_names_str = " & ".join(c['name'] for c in character_refs)
        result = MangaResult(
            manga_id="",
            character_name=char_names_str,
            style=style,
        )

        async for event in self.generate_manga_streaming(
            character_refs=character_refs,
            story_beats=story_beats,
            dialogues=dialogues,
            style=style,
        ):
            if event.type == 'start':
                result.manga_id = event.data['manga_id']
            elif event.type == 'panel':
                result.panels.append(MangaPanel(
                    index=event.data['panel_index'],
                    story_beat=event.data['story_beat'],
                    dialogue=event.data['dialogue'],
                    image_url=event.data['image_url'],
                ))
            elif event.type == 'complete':
                result.generation_time_seconds = event.data['generation_time']
            elif event.type == 'error':
                raise RuntimeError(event.data['message'])

        return result
