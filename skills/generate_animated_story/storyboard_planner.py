"""
Storyboard Planner - Analyzes manga panels and generates animation directions.

This pre-processing step ensures:
1. Consistent character appearance across all clips
2. Appropriate duration per clip (4/6/8s)
3. Specific motion direction per panel
4. Smooth transitions between clips
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from config import GOOGLE_API_KEY, GEMINI_MODEL
from skills.generate_manga.generate_manga import MangaPanel

logger = logging.getLogger(__name__)


@dataclass
class LyricsResult:
    """Generated song lyrics and style tags for music generation."""
    tags: str       # Style/genre description for ElevenLabs positive_global_styles
    lyrics: str     # Song lyrics with [Verse]/[Chorus] structure tags
    mood: str       # One-word mood summary
    bpm: int = 0    # Suggested BPM (0 = let model decide)
    vocal_style: str = ""  # Vocal delivery descriptor (e.g. "breathy", "energetic")
    negative_tags: str = ""  # Styles to avoid (for negative_global_styles)


@dataclass
class PanelAnimationPlan:
    """Animation plan for a single panel."""
    panel_index: int
    story_beat: str
    dialogue: Optional[str]

    # Animation direction
    duration_seconds: int  # 4, 6, or 8
    motion_type: str  # "subtle", "moderate", "dynamic"
    camera_movement: str  # "static", "slow_push", "slow_pull", "pan_left", "pan_right", "tilt_up", "tilt_down"
    subject_motion: str  # Specific character animation: "breathing only", "turns head left", "reaches forward"

    # Context for consistency
    key_visual_elements: str  # "blue scarf, sunny park, cherry blossoms"
    emotion: str  # "curious", "excited", "peaceful"

    # Transitions
    transition_in: str  # How this clip starts relative to previous
    transition_out: str  # How this clip ends (setup for next)


@dataclass
class StoryboardPlan:
    """Complete animation plan for all panels."""
    total_duration: int
    panel_plans: list[PanelAnimationPlan]
    consistency_notes: str  # Global notes for character consistency
    overall_mood: str  # "adventurous", "peaceful", "dramatic"


class StoryboardPlanner:
    """
    Analyzes manga panels and creates detailed animation plans.

    Uses Gemini to understand the visual content and story flow,
    then generates appropriate motion direction for Veo.
    """

    def __init__(self, client: genai.Client = None):
        self.client = client or genai.Client(api_key=GOOGLE_API_KEY)
        self.model = GEMINI_MODEL

    async def plan_animation(
        self,
        panels: list[MangaPanel],
        panel_paths: list[Path],
        character_sheets: list[Path],
        character_name: str,
    ) -> StoryboardPlan:
        """
        Analyze all panels and create animation plan.

        Args:
            panels: MangaPanel objects with story_beat and dialogue
            panel_paths: Paths to panel images
            character_sheets: Character reference images
            character_name: Main character name

        Returns:
            StoryboardPlan with per-panel animation directions
        """
        logger.info(f"[StoryboardPlanner] Planning animation for {len(panels)} panels")

        # Build content parts with all images
        content_parts = []

        # Add character sheets first
        for i, sheet_path in enumerate(character_sheets[:2]):
            if sheet_path and sheet_path.exists():
                with open(sheet_path, 'rb') as f:
                    img_data = f.read()
                mime = 'image/png' if str(sheet_path).endswith('.png') else 'image/jpeg'
                img = types.Part.from_bytes(data=img_data, mime_type=mime)
                content_parts.append(types.Part.from_text(text=f"[CHARACTER REFERENCE {i+1}]: {character_name}"))
                content_parts.append(img)

        # Add all panels with their story context
        for i, (panel, path) in enumerate(zip(panels, panel_paths)):
            if path and path.exists():
                with open(path, 'rb') as f:
                    img_data = f.read()
                mime = 'image/png' if str(path).endswith('.png') else 'image/jpeg'
                img = types.Part.from_bytes(data=img_data, mime_type=mime)
                panel_context = f"""[PANEL {i+1}]
Story beat: {panel.story_beat or 'Scene moment'}
Dialogue: {panel.dialogue or 'None'}"""
                content_parts.append(types.Part.from_text(text=panel_context))
                content_parts.append(img)

        # Add the planning prompt
        planning_prompt = self._build_planning_prompt(panels, character_name)
        content_parts.append(types.Part.from_text(text=planning_prompt))

        # Call Gemini
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=content_parts,
                config=types.GenerateContentConfig(
                    temperature=0.7,  # Some creativity but structured
                    response_mime_type="application/json",
                ),
            )

            # Parse JSON response
            plan_data = json.loads(response.text)
            return self._parse_plan(plan_data, panels)

        except Exception as e:
            logger.error(f"[StoryboardPlanner] Planning failed: {e}")
            # Return default plan
            return self._create_default_plan(panels)

    async def generate_lyrics_and_tags(
        self,
        panels: list[MangaPanel],
        character_name: str = "",
        story_summary: str = "",
    ) -> LyricsResult:
        """
        Generate song lyrics and style tags for ElevenLabs music generation.

        Uses Gemini to create short, singable English lyrics that match
        the story's mood and content, plus style descriptions for ElevenLabs.

        Args:
            panels: MangaPanel objects with story_beat and dialogue
            character_name: Main character name (for context)
            story_summary: Brief story description (for context)

        Returns:
            LyricsResult with tags (ElevenLabs positive_global_styles), lyrics, and mood
        """
        logger.info(f"[StoryboardPlanner] Generating lyrics for {len(panels)} panels")

        # Build story context from panels with arc roles
        arc_roles = ["setup", "action", "twist", "payoff"]
        panel_context = []
        for i, panel in enumerate(panels):
            beat = panel.story_beat or "Scene moment"
            dialogue = panel.dialogue or "No dialogue"
            role = arc_roles[i] if i < len(arc_roles) else "moment"
            panel_context.append(f"Panel {i+1} ({role}): {beat} | Dialogue: {dialogue}")

        panels_text = "\n".join(panel_context)

        prompt = f"""You are a songwriter creating a short background song for an animated manga video.
The song will be generated by an AI music model (ElevenLabs) that understands musical terminology.

STORY CONTEXT:
Character: {character_name or "Main character"}
Summary: {story_summary or "A short manga story"}

PANELS (each panel = 4 seconds of video, 16 seconds total):
{panels_text}

TASK: Write exactly 4 short lyric lines — one per panel — that follow the story progression.
Each line is sung over a 4-second section. At singing speed, 3-5 words fit in 4 seconds.
The AI music model fills gaps with melody and instrumental.

SONG STRUCTURE (4 sections, one per panel):
- [Verse 1] Line 1 → Panel 1 (setup) — gentle, building
- [Verse 2] Line 2 → Panel 2 (action) — rising energy
- [Chorus] Line 3 → Panel 3 (twist) — energetic, catchy hook
         Line 4 → Panel 4 (payoff) — triumphant, uplifting

LYRICS REQUIREMENTS:
1. EXACTLY 4 lines — no more, no less
2. Each line: 3-5 words max (must fit in 4 seconds of singing)
3. Each line captures its panel's specific story beat — not generic vibes
4. Common, simple English words that are easy to sing
5. Fun and playful tone — think anime OP hook, not a ballad
6. Lines should flow as a song when read together
7. English only

STYLE TAGS — These control the music model's output. Be specific and musical:
- "tags": Comma-separated style descriptors for the whole song.
  Use intent-based language: genre, instrumentation, vocal style, energy level.
  Example: "upbeat anime pop, bright female vocals, piano, acoustic guitar, energetic, 130 BPM"
- "vocal_style": One vocal delivery descriptor that matches the character's persona.
  Options: "breathy", "energetic", "raw", "gentle", "playful", "confident", "warm", "excited"
  Pick the one that best fits {character_name or "the character"}'s personality.
- "bpm": Suggested tempo (80-160). Match the story energy:
  80-100 = calm/emotional, 100-120 = moderate, 120-140 = upbeat, 140-160 = high energy
- "negative_tags": Styles to AVOID (comma-separated).
  Example: "slow, dark, heavy metal, sad, spoken word, lo-fi"
- "mood": A single word for the overall mood

EXAMPLE for a "treasure hunt" story:
{{
    "tags": "anime pop, bright female vocals, piano, acoustic guitar, playful, 125 BPM, C major",
    "lyrics": "[Verse 1]\\nLook a treasure map\\n[Verse 2]\\nOff into the woods\\n[Chorus]\\nWe found the hidden gold\\nBest adventure ever",
    "vocal_style": "excited",
    "bpm": 125,
    "negative_tags": "slow, dark, heavy metal, sad, spoken word",
    "mood": "adventurous"
}}

Respond with JSON:
{{
    "tags": "genre, instruments, vocal type, energy, BPM, optional key",
    "lyrics": "[Verse 1]\\nLine 1\\n[Verse 2]\\nLine 2\\n[Chorus]\\nLine 3\\nLine 4",
    "vocal_style": "delivery_descriptor",
    "bpm": 120,
    "negative_tags": "styles to avoid",
    "mood": "mood_word"
}}"""

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                ),
            )

            data = json.loads(response.text)
            result = LyricsResult(
                tags=data.get("tags", "anime pop, female vocals, piano"),
                lyrics=data.get("lyrics", self._fallback_lyrics()),
                mood=data.get("mood", "hopeful"),
                bpm=data.get("bpm", 0),
                vocal_style=data.get("vocal_style", ""),
                negative_tags=data.get("negative_tags", ""),
            )
            logger.info(
                f"[StoryboardPlanner] Lyrics generated: mood={result.mood}, "
                f"bpm={result.bpm}, vocal={result.vocal_style}, "
                f"{len(result.lyrics.splitlines())} lines"
            )
            return result

        except Exception as e:
            logger.error(f"[StoryboardPlanner] Lyrics generation failed: {e}")
            return LyricsResult(
                tags="anime pop, female vocals, piano, gentle, 110 BPM",
                lyrics=self._fallback_lyrics(),
                mood="hopeful",
                bpm=110,
                vocal_style="gentle",
                negative_tags="slow, dark, heavy metal, sad, spoken word",
            )

    def _fallback_lyrics(self) -> str:
        """Fallback lyrics when generation fails. 4 lines matching panel arc."""
        return (
            "[Verse 1]\n"
            "Shining in the light\n"
            "[Verse 2]\n"
            "Running side by side\n"
            "[Chorus]\n"
            "We can fly together\n"
            "Nothing holds us down"
        )

    def _build_planning_prompt(self, panels: list[MangaPanel], character_name: str) -> str:
        """Build the prompt for animation planning."""
        return f"""You are a professional animation director planning a short anime video.

Analyze the character reference sheets and manga panels provided, then create a detailed animation plan.

CHARACTER: {character_name}

TASK: Create an animation plan for each panel that will be turned into video clips using Veo 3.1.

FOR EACH PANEL, determine:

1. **duration_seconds**: Choose 4, 6, or 8 seconds based on ideal pacing:
   - 4s: Quick reaction, simple emotion, no dialogue
   - 6s: Moderate action, short dialogue, building moment
   - 8s: Complex action, longer dialogue, dramatic moment
   NOTE: Veo 3.1 with reference_images forces 8s, but this helps plan post-trimming.

2. **motion_type**: How much movement overall
   - "subtle": Breathing, blinking, hair sway only
   - "moderate": Head turns, gestures, weight shifts
   - "dynamic": Full body movement, action poses

3. **camera_movement**: Pick ONE camera move
   - "static": No camera movement
   - "slow_push": Slowly zoom in (builds intensity)
   - "slow_pull": Slowly zoom out (reveals context)
   - "pan_left" / "pan_right": Horizontal movement
   - "tilt_up" / "tilt_down": Vertical movement
   - "orbit_slight": Very subtle rotation around subject

4. **subject_motion**: Specific animation for {character_name}
   - Be SPECIFIC: "tilts head right curiously", "ears perk up", "tail wags slowly"
   - Match the story beat and emotion
   - Consider what the character would naturally do

5. **emotion**: The dominant emotion to convey
   - Examples: "curious", "excited", "peaceful", "surprised", "determined"

6. **key_visual_elements**: Important visual details to maintain
   - List clothing, accessories, environment details

7. **transition_in**: How this clip connects FROM the previous
   - "cut": Direct cut from previous
   - "continuation": Continues motion from previous
   - "reaction": Reacting to previous scene

8. **transition_out**: How this clip sets up the next
   - "hold": Hold final pose
   - "motion_toward": Moving toward next scene's setup
   - "look_direction": Character looks toward next scene's focus

IMPORTANT CONSISTENCY RULES:
- {character_name}'s appearance MUST match the character reference sheet EXACTLY
- Colors, proportions, clothing must be identical across all clips
- If {character_name} is an animal, use animal behaviors (ear movement, tail, etc.)

Respond with JSON:
{{
    "overall_mood": "the general mood of this story",
    "consistency_notes": "key visual details that must stay consistent across all clips",
    "panel_plans": [
        {{
            "panel_index": 0,
            "duration_seconds": 4|6|8,
            "motion_type": "subtle|moderate|dynamic",
            "camera_movement": "static|slow_push|slow_pull|pan_left|pan_right|tilt_up|tilt_down|orbit_slight",
            "subject_motion": "specific motion description",
            "emotion": "emotion word",
            "key_visual_elements": "list of visual elements",
            "transition_in": "cut|continuation|reaction",
            "transition_out": "hold|motion_toward|look_direction"
        }},
        ...
    ]
}}"""

    def _parse_plan(self, plan_data: dict, panels: list[MangaPanel]) -> StoryboardPlan:
        """Parse JSON response into StoryboardPlan."""
        panel_plans = []

        for i, pp in enumerate(plan_data.get("panel_plans", [])):
            if i >= len(panels):
                break

            panel = panels[i]
            panel_plans.append(PanelAnimationPlan(
                panel_index=i,
                story_beat=panel.story_beat or "",
                dialogue=panel.dialogue,
                duration_seconds=pp.get("duration_seconds", 6),
                motion_type=pp.get("motion_type", "subtle"),
                camera_movement=pp.get("camera_movement", "static"),
                subject_motion=pp.get("subject_motion", "subtle breathing"),
                key_visual_elements=pp.get("key_visual_elements", ""),
                emotion=pp.get("emotion", "neutral"),
                transition_in=pp.get("transition_in", "cut"),
                transition_out=pp.get("transition_out", "hold"),
            ))

        total_duration = sum(p.duration_seconds for p in panel_plans)

        return StoryboardPlan(
            total_duration=total_duration,
            panel_plans=panel_plans,
            consistency_notes=plan_data.get("consistency_notes", ""),
            overall_mood=plan_data.get("overall_mood", ""),
        )

    def _create_default_plan(self, panels: list[MangaPanel]) -> StoryboardPlan:
        """Create a default plan when Gemini planning fails."""
        panel_plans = []

        for i, panel in enumerate(panels):
            # Estimate duration from dialogue length
            dialogue_len = len(panel.dialogue.split()) if panel.dialogue else 0
            if dialogue_len > 15:
                duration = 8
            elif dialogue_len > 5:
                duration = 6
            else:
                duration = 4

            panel_plans.append(PanelAnimationPlan(
                panel_index=i,
                story_beat=panel.story_beat or "",
                dialogue=panel.dialogue,
                duration_seconds=duration,
                motion_type="subtle",
                camera_movement="slow_push" if i == len(panels) - 1 else "static",
                subject_motion="gentle breathing, soft eye blinks",
                key_visual_elements="",
                emotion="neutral",
                transition_in="cut",
                transition_out="hold",
            ))

        return StoryboardPlan(
            total_duration=sum(p.duration_seconds for p in panel_plans),
            panel_plans=panel_plans,
            consistency_notes="Maintain character appearance from reference sheet",
            overall_mood="neutral",
        )


def build_veo_motion_prompt(plan: PanelAnimationPlan, consistency_notes: str) -> str:
    """
    Convert a PanelAnimationPlan into a Veo-ready motion prompt.

    This is used by generate_video.py to create the animation instructions.
    """
    camera_descriptions = {
        "static": "Camera: Locked off, no movement",
        "slow_push": "Camera: Very slow push in toward subject (5% closer over duration)",
        "slow_pull": "Camera: Very slow pull out from subject (5% wider over duration)",
        "pan_left": "Camera: Slow pan left, following or revealing",
        "pan_right": "Camera: Slow pan right, following or revealing",
        "tilt_up": "Camera: Slow tilt upward",
        "tilt_down": "Camera: Slow tilt downward",
        "orbit_slight": "Camera: Very subtle orbit around subject (5 degrees max)",
    }

    motion_intensity = {
        "subtle": "Keep motion minimal - breathing, blinking, hair sway only",
        "moderate": "Allow natural movement - gestures, head turns, weight shifts",
        "dynamic": "Full animation - body movement, expressive poses, action",
    }

    return f"""=== ANIMATION DIRECTION ===

{camera_descriptions.get(plan.camera_movement, "Camera: Static")}

Subject motion: {plan.subject_motion}
Intensity: {motion_intensity.get(plan.motion_type, "subtle")}
Emotion to convey: {plan.emotion}

Transition: {plan.transition_in} from previous → {plan.transition_out} to next

=== CONSISTENCY (CRITICAL) ===
{consistency_notes}
Visual elements to maintain: {plan.key_visual_elements}

Do NOT change character appearance. Match reference sheet EXACTLY."""
