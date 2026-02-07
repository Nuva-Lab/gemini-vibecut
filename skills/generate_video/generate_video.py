"""
Video Generation Skill - Veo 3.1 video generation from manga keyframes.

This skill generates animated video clips from manga panels using:
- Panel image as starting keyframe (image-to-video)
- Duration matched to TTS audio
- Subtle animation (breathing, hair movement, camera drift)

NOTE: Veo uses async operations pattern (generate_videos + polling), not generate_content.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from config import (
    GOOGLE_API_KEY,
    VEO_MODEL,
    OUTPUT_DIR,
    VIDEO_DURATION_SECONDS,
    MIN_CLIP_DURATION_SECONDS,
    MAX_CLIP_DURATION_SECONDS,
)
from models.character import Character
from models.world import World
from agent.prompts import Prompts

logger = logging.getLogger(__name__)

# Veo polling settings
VEO_POLL_INTERVAL_SECONDS = 10
VEO_MAX_WAIT_SECONDS = 300  # 5 minutes max


@dataclass
class VideoClipResult:
    """Result of generating a video clip."""
    video_path: Path
    duration_seconds: float
    keyframe_path: Optional[Path]
    clip_index: int


class VideoGenerator:
    """
    Generate animated video clips using Veo 3.1.

    Key capability: Image-to-video with starting frame preservation.
    The manga panel becomes the first frame, then subtle animation is added.
    """

    def __init__(self, client: genai.Client = None):
        """Initialize with Gemini/Veo client."""
        self.client = client or genai.Client(api_key=GOOGLE_API_KEY)
        self.model = VEO_MODEL
        self.output_dir = OUTPUT_DIR / "videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _clamp_duration(self, duration: float) -> tuple[float, str]:
        """
        Clamp duration to valid range for video generation.

        Returns:
            (clamped_duration, adjustment_note)
        """
        if duration < MIN_CLIP_DURATION_SECONDS:
            return MIN_CLIP_DURATION_SECONDS, "extended"
        elif duration > MAX_CLIP_DURATION_SECONDS:
            return MAX_CLIP_DURATION_SECONDS, "capped"
        else:
            return duration, "exact"

    def _build_animation_prompt(self, motion_description: str = None) -> str:
        """Build the animation instruction prompt."""
        base = """ANIMATION STYLE:
- Subtle breathing, hair movement, eye blinks
- Soft clothing sway as if light breeze
- Slow camera drift or gentle push
- Preserve character design and art style exactly

CRITICAL - PRESERVE:
- Character proportions and design
- Art style (anime/manga aesthetic)
- Color palette and lighting
- Background composition

DO NOT:
- Change character appearance
- Add dramatic camera movements
- Apply heavy filters or style changes
- Create jarring or fast movements
"""
        if motion_description:
            # Merge base style with story context
            return base + "\n" + motion_description

        # Default subtle animation for anime panels
        return base + "\nGeneric ambient animation with subtle motion."

    def _build_living_image_prompt(self, story_beat: str = None) -> str:
        """
        Build a minimal prompt for "living image" style animation.

        Same image as start+end frame = Veo adds subtle motion without morphing.
        Keep prompt SHORT and focused on subtle animation only.
        """
        prompt = """Animate this illustration with subtle, lifelike motion.

KEEP THE IMAGE EXACTLY THE SAME - only add subtle animation:
- Gentle breathing motion
- Soft eye blinks (1-2 times)
- Slight hair/fur movement
- Subtle clothing sway
- Tiny ambient motion in background

DO NOT:
- Change character poses
- Move characters to different positions
- Change facial expressions dramatically
- Add any new elements
- Change the composition

The start and end frame are IDENTICAL - create a seamless loop of subtle life.

AUDIO: Soft ambient sounds only. NO speech, NO music."""

        return prompt

    async def generate_clip_from_keyframe(
        self,
        keyframe_path: Path,
        duration_seconds: float,
        motion_description: str = None,
        clip_index: int = 0,
    ) -> VideoClipResult:
        """
        Generate a video clip starting from a keyframe image.

        Uses the manga panel as the first frame and adds subtle animation.
        Veo uses async operations: generate_videos() + polling.

        Args:
            keyframe_path: Path to manga panel image (9:16)
            duration_seconds: Target duration (typically from TTS audio)
            motion_description: Optional custom motion instructions
            clip_index: Index of this clip in sequence

        Returns:
            VideoClipResult with video path and actual duration
        """
        # Clamp duration to valid range
        duration, adjustment = self._clamp_duration(duration_seconds)
        if adjustment != "exact":
            logger.info(f"[VideoGenerator] Duration {adjustment}: {duration_seconds:.1f}s -> {duration:.1f}s")

        # Load keyframe image
        if not keyframe_path.exists():
            raise FileNotFoundError(f"Keyframe not found: {keyframe_path}")

        # Load image for Veo using SDK's Image type
        veo_image = types.Image.from_file(location=str(keyframe_path))

        # Build animation prompt
        animation_instructions = self._build_animation_prompt(motion_description)

        prompt = f"""Animate this anime scene with subtle, living motion:

{animation_instructions}

Keep the first frame exactly as the input image. Create smooth {duration:.1f} second animation."""

        logger.info(f"[VideoGenerator] Generating clip {clip_index + 1} ({duration:.1f}s) from {keyframe_path.name}")

        def start_veo_operation():
            """Start Veo video generation (returns operation for polling)."""
            return self.client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                image=veo_image,
                config=types.GenerateVideosConfig(
                    aspect_ratio="9:16",  # Vertical for phone/manga
                ),
            )

        def poll_operation(operation):
            """Poll until operation completes."""
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > VEO_MAX_WAIT_SECONDS:
                    raise TimeoutError(f"Veo generation timed out after {VEO_MAX_WAIT_SECONDS}s")

                logger.info(f"[VideoGenerator] Waiting for clip {clip_index + 1}... ({elapsed:.0f}s)")
                time.sleep(VEO_POLL_INTERVAL_SECONDS)
                operation = self.client.operations.get(operation)

            return operation

        try:
            # Start generation
            operation = await asyncio.to_thread(start_veo_operation)
            logger.info(f"[VideoGenerator] Veo operation started for clip {clip_index + 1}")

            # Poll until complete
            operation = await asyncio.to_thread(poll_operation, operation)
            logger.info(f"[VideoGenerator] Clip {clip_index + 1} generation complete")

        except Exception as e:
            logger.error(f"[VideoGenerator] Veo API error: {e}")
            raise RuntimeError(f"Veo generation failed: {e}")

        # Extract video from response
        if not operation.response or not operation.response.generated_videos:
            raise RuntimeError("Veo generation failed - no video in response")

        video = operation.response.generated_videos[0]

        # Save video file
        video_id = str(uuid.uuid4())[:8]
        video_filename = f"clip_{clip_index + 1}_{video_id}.mp4"
        video_path = self.output_dir / video_filename

        # Download and save
        self.client.files.download(file=video.video)
        video.video.save(str(video_path))

        logger.info(f"[VideoGenerator] Clip saved: {video_filename} ({duration:.1f}s)")

        return VideoClipResult(
            video_path=video_path,
            duration_seconds=duration,
            keyframe_path=keyframe_path,
            clip_index=clip_index,
        )

    def _estimate_duration_from_dialogue(self, dialogue: str) -> int:
        """
        Estimate Veo duration based on dialogue length.

        Veo 3.1 supports: 4, 6, or 8 second durations.
        """
        if not dialogue or not dialogue.strip():
            return 4  # Silent scene: 4 seconds

        # Rough estimate: ~150 words per minute = 2.5 words/second
        word_count = len(dialogue.split())
        estimated_seconds = word_count / 2.5

        # Clamp to Veo's supported durations
        if estimated_seconds <= 4:
            return 4
        elif estimated_seconds <= 6:
            return 6
        else:
            return 8

    def _dialogue_to_animal_emotion(self, dialogue: str, character_name: str) -> str:
        """Convert dialogue text to animal emotion description."""
        if not dialogue:
            return f"{character_name} reacts to the scene with natural animal behavior"

        # Extract emotion cues from punctuation and keywords
        text = dialogue.lower()

        # Detect emotion from punctuation
        if "!" in dialogue and ("wow" in text or "amazing" in text or "great" in text):
            emotion = "excited"
            action = "barks/meows excitedly, tail wagging energetically"
        elif "!" in dialogue and ("no" in text or "stop" in text or "wait" in text):
            emotion = "alarmed"
            action = "barks/meows urgently, body alert and tense"
        elif "?" in dialogue:
            emotion = "curious"
            action = "tilts head curiously, ears perked up"
        elif "..." in dialogue or ("sad" in text or "sorry" in text or "miss" in text):
            emotion = "melancholy"
            action = "whimpers softly, ears drooping slightly"
        elif "haha" in text or "funny" in text or "laugh" in text:
            emotion = "playful"
            action = "makes happy sounds, bouncing playfully"
        elif "love" in text or "friend" in text or "happy" in text:
            emotion = "affectionate"
            action = "nuzzles warmly, making contented sounds"
        elif "scared" in text or "afraid" in text or "help" in text:
            emotion = "worried"
            action = "whines nervously, looking around cautiously"
        else:
            # Default based on exclamation marks
            if dialogue.count("!") >= 2:
                emotion = "very excited"
                action = "makes enthusiastic sounds, full of energy"
            elif "!" in dialogue:
                emotion = "engaged"
                action = "responds with interested sounds"
            else:
                emotion = "attentive"
                action = "watches attentively, making soft sounds"

        return f"{character_name} {action}, expressing {emotion}"

    async def generate_clip_with_references(
        self,
        keyframe_path: Path,
        reference_images: list[Path] = None,
        dialogue: str = None,
        story_context: str = None,
        character_name: str = None,
        source_type: str = None,  # NEW: "pet" or "person"
        persona: str = None,  # NEW: character personality
        duration_seconds: int = None,
        clip_index: int = 0,
        next_panel_path: Path = None,
    ) -> VideoClipResult:
        """
        Generate video clip using Veo 3.1 multi-image reference mode + native audio.

        Docs: https://ai.google.dev/gemini-api/docs/video?example=dialogue#reference-images

        Uses reference_images (max 3) for character/scene consistency.
        Both veo-3.1-generate-preview and veo-3.1-fast-generate-preview support this.

        VALIDATED CONSTRAINTS (via test_veo_refs_v2.py):
        - Max 3 reference images (API enforced)
        - Duration is optional (defaults work)
        - NO `image` parameter when using reference_images

        Args:
            keyframe_path: Panel image as reference (scene composition)
            reference_images: Additional refs (e.g., character sheet). Combined max 3.
            dialogue: Character dialogue for native audio
            story_context: Scene description
            character_name: Speaking character name
            source_type: Character type ("pet" for animal sounds, "person" for speech)
            persona: Character personality description
            duration_seconds: Optional duration (default works fine)
            clip_index: Index for logging/naming
            next_panel_path: Optional additional panel reference

        Returns:
            VideoClipResult with video path (includes native audio!)
        """
        # Verify panel exists
        if not keyframe_path.exists():
            raise FileNotFoundError(f"Panel not found: {keyframe_path}")

        # Default duration for result tracking (API uses its own default)
        if duration_seconds is None:
            duration_seconds = 8  # Veo default

        logger.info(f"[VideoGenerator] Generating clip {clip_index + 1} using multi-image reference mode")

        # Build reference images (max 3 per API) with explicit indexing
        refs = []
        ref_descriptions = []  # Track what each ref is for prompt clarity

        # Reference 1: Panel (defines scene composition)
        panel_image = types.Image.from_file(location=str(keyframe_path))
        refs.append(types.VideoGenerationReferenceImage(
            image=panel_image,
            reference_type="asset"
        ))
        ref_descriptions.append("Image 1: Scene panel (use for composition, poses, framing)")
        logger.info(f"[VideoGenerator] Reference 1 (panel): {keyframe_path.name}")

        # Reference 2-3: Character sheets if provided
        char_names_for_refs = []
        if reference_images and len(refs) < 3:
            for idx, ref_path in enumerate(reference_images[:2]):  # Can add up to 2 more refs
                if ref_path and ref_path.exists() and len(refs) < 3:
                    ref_image = types.Image.from_file(location=str(ref_path))
                    refs.append(types.VideoGenerationReferenceImage(
                        image=ref_image,
                        reference_type="asset"
                    ))
                    # Extract character name from filename if possible
                    char_ref_name = f"Character {idx + 1}"
                    ref_descriptions.append(f"Image {len(refs)}: {char_ref_name} reference sheet (use for character appearance)")
                    char_names_for_refs.append(char_ref_name)
                    logger.info(f"[VideoGenerator] Reference {len(refs)} (character): {ref_path.name}")

        logger.info(f"[VideoGenerator] Total refs: {len(refs)}")

        # Build enhanced structured prompt with explicit ref indexing
        prompt_parts = []

        # === REFERENCE IMAGE INDEX === (Critical for model to understand refs)
        prompt_parts.append(f"""=== REFERENCE IMAGES ({len(refs)} provided) ===
{chr(10).join(ref_descriptions)}

IMPORTANT:
- Do NOT change character appearance from reference sheets
- Use panel composition EXACTLY as shown
- Character proportions, colors, outfit must match reference sheets precisely""")

        # === SCENE ===
        if story_context:
            prompt_parts.append(f"\n=== SCENE ===\n{story_context}")

        # === ANIMATION ===
        prompt_parts.append("""
=== ANIMATION ===
Motion type: Subtle, lifelike animation
Key movements:
- Natural breathing rhythm
- Soft eye blinks and micro-expressions
- Gentle hair/fur movement as if light breeze
- Subtle body sway or weight shifts
- Ears and tail movement (if animal)

Style:
- Smooth, fluid motion (no jarring cuts)
- Preserve anime aesthetic throughout
- Keep character on-model at all times""")

        # === AUDIO === Music video mode: ambient sounds only, NO dialogue
        # Note: We skip all dialogue - will add music separately in post-production
        prompt_parts.append("""
=== AUDIO ===
MUSIC VIDEO MODE - No dialogue, ambient sounds only

Sound direction:
- Natural ambient sounds matching the scene (wind, nature, environment)
- Soft sound effects where appropriate (footsteps, rustling, etc.)
- NO speech, NO dialogue, NO voice, NO talking
- NO background music, NO musical score, NO soundtrack
- Silent or near-silent is preferred""")

        prompt = "\n".join(prompt_parts)
        logger.debug(f"[VideoGenerator] Prompt:\n{prompt[:500]}...")

        # Multi-image reference mode config
        # IMPORTANT: When using reference_images, duration MUST be 8 seconds
        # See: https://ai.google.dev/gemini-api/docs/video
        # "Must be '8' when using extension, reference images or with 1080p and 4k resolutions."
        config_kwargs = {
            "aspect_ratio": "9:16",
            "reference_images": refs,
            "duration_seconds": 8,  # REQUIRED: 8s with reference_images mode
        }

        # Update duration_seconds for return value
        duration_seconds = 8
        logger.info(f"[VideoGenerator] Using multi-image reference mode with {len(refs)} refs (forced 8s duration)")

        def start_veo_operation():
            """Start Veo video generation with reference images."""
            return self.client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                # NO image= param when using reference_images
                config=types.GenerateVideosConfig(**config_kwargs),
            )

        def poll_operation(operation):
            """Poll until operation completes."""
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > VEO_MAX_WAIT_SECONDS:
                    raise TimeoutError(f"Veo generation timed out after {VEO_MAX_WAIT_SECONDS}s")

                logger.info(f"[VideoGenerator] Waiting for clip {clip_index + 1}... ({elapsed:.0f}s)")
                time.sleep(VEO_POLL_INTERVAL_SECONDS)
                operation = self.client.operations.get(operation)

            return operation

        try:
            # Start generation
            operation = await asyncio.to_thread(start_veo_operation)
            logger.info(f"[VideoGenerator] Veo operation started for clip {clip_index + 1} (refs: {len(refs)})")

            # Poll until complete
            operation = await asyncio.to_thread(poll_operation, operation)
            logger.info(f"[VideoGenerator] Clip {clip_index + 1} generation complete")

        except Exception as e:
            logger.error(f"[VideoGenerator] Veo API error: {e}")
            # Return None video path to indicate failure
            return VideoClipResult(
                video_path=None,
                duration_seconds=duration_seconds,
                keyframe_path=keyframe_path,
                clip_index=clip_index,
            )

        # Extract video from response
        if not operation.response or not operation.response.generated_videos:
            # Log detailed response for debugging
            if operation.response:
                logger.error(f"[VideoGenerator] Veo response has no videos. Response: {operation.response}")
            else:
                logger.error("[VideoGenerator] Veo response is None/empty")
            logger.error("[VideoGenerator] Veo generation failed - no video in response")
            return VideoClipResult(
                video_path=None,
                duration_seconds=duration_seconds,
                keyframe_path=keyframe_path,
                clip_index=clip_index,
            )

        video = operation.response.generated_videos[0]

        # Save video file
        video_id = str(uuid.uuid4())[:8]
        video_filename = f"clip_{clip_index + 1}_{video_id}_ref.mp4"
        video_path = self.output_dir / video_filename

        # Download and save
        self.client.files.download(file=video.video)
        video.video.save(str(video_path))

        logger.info(f"[VideoGenerator] Clip saved with native audio: {video_filename} ({duration_seconds}s)")

        return VideoClipResult(
            video_path=video_path,
            duration_seconds=duration_seconds,
            keyframe_path=keyframe_path,
            clip_index=clip_index,
        )

    async def generate_clips_batch(
        self,
        keyframes: list[Path],
        durations: list[float],
        motion_descriptions: list[str] = None,
    ) -> list[VideoClipResult]:
        """
        Generate multiple video clips in sequence.

        Args:
            keyframes: List of manga panel image paths
            durations: Corresponding durations (from TTS)
            motion_descriptions: Optional per-clip motion hints

        Returns:
            List of VideoClipResult in order
        """
        if len(keyframes) != len(durations):
            raise ValueError(f"Keyframes ({len(keyframes)}) and durations ({len(durations)}) must have same length")

        motion_descriptions = motion_descriptions or [None] * len(keyframes)

        results = []
        for i, (keyframe, duration, motion) in enumerate(
            zip(keyframes, durations, motion_descriptions)
        ):
            try:
                result = await self.generate_clip_from_keyframe(
                    keyframe_path=keyframe,
                    duration_seconds=duration,
                    motion_description=motion,
                    clip_index=i,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"[VideoGenerator] Failed to generate clip {i + 1}: {e}")
                # Continue with other clips, don't fail entire batch
                results.append(VideoClipResult(
                    video_path=None,
                    duration_seconds=duration,
                    keyframe_path=keyframe,
                    clip_index=i,
                ))

        return results

    async def generate_interpolation_clip(
        self,
        first_frame_path: Path,
        last_frame_path: Path,
        story_context: str = None,
        character_descriptions: list[str] = None,
        first_story_beat: str = None,
        last_story_beat: str = None,
        style: str = "anime",
        clip_index: int = 0,
    ) -> VideoClipResult:
        """
        Generate video clip by interpolating between first and last frame.

        This is the preferred method for smooth, consistent animations.
        Veo morphs between the two endpoints, creating natural transitions.

        Args:
            first_frame_path: Starting panel image
            last_frame_path: Ending panel image
            story_context: Optional context for the transition
            character_descriptions: List of character visual descriptions
            first_story_beat: What's happening in the first frame
            last_story_beat: What's happening in the last frame
            style: Visual style (anime, ghibli, etc.)
            clip_index: Index for logging/naming

        Returns:
            VideoClipResult with video path (8s duration)
        """
        if not first_frame_path.exists():
            raise FileNotFoundError(f"First frame not found: {first_frame_path}")
        if not last_frame_path.exists():
            raise FileNotFoundError(f"Last frame not found: {last_frame_path}")

        logger.info(f"[VideoGenerator] Generating interpolation clip {clip_index + 1}: {first_frame_path.name} → {last_frame_path.name}")

        # Load images
        first_image = types.Image.from_file(location=str(first_frame_path))
        last_image = types.Image.from_file(location=str(last_frame_path))

        # Build detailed, structured prompt
        prompt = self._build_interpolation_prompt(
            story_context=story_context,
            character_descriptions=character_descriptions,
            first_story_beat=first_story_beat,
            last_story_beat=last_story_beat,
            style=style,
            clip_index=clip_index,
        )

        logger.debug(f"[VideoGenerator] Interpolation prompt ({len(prompt)} chars):\n{prompt[:500]}...")

        def start_veo_operation():
            """Start Veo interpolation."""
            return self.client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                image=first_image,
                config=types.GenerateVideosConfig(
                    aspect_ratio="9:16",
                    last_frame=last_image,
                ),
            )

        def poll_operation(operation):
            """Poll until operation completes."""
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > VEO_MAX_WAIT_SECONDS:
                    raise TimeoutError(f"Veo generation timed out after {VEO_MAX_WAIT_SECONDS}s")

                logger.info(f"[VideoGenerator] Waiting for interpolation clip {clip_index + 1}... ({elapsed:.0f}s)")
                time.sleep(VEO_POLL_INTERVAL_SECONDS)
                operation = self.client.operations.get(operation)

            return operation

        try:
            operation = await asyncio.to_thread(start_veo_operation)
            logger.info(f"[VideoGenerator] Veo interpolation started for clip {clip_index + 1}")

            operation = await asyncio.to_thread(poll_operation, operation)
            logger.info(f"[VideoGenerator] Interpolation clip {clip_index + 1} complete")

        except Exception as e:
            logger.error(f"[VideoGenerator] Veo interpolation error: {e}")
            return VideoClipResult(
                video_path=None,
                duration_seconds=8,
                keyframe_path=first_frame_path,
                clip_index=clip_index,
            )

        if not operation.response or not operation.response.generated_videos:
            logger.error("[VideoGenerator] Veo interpolation failed - no video in response")
            return VideoClipResult(
                video_path=None,
                duration_seconds=8,
                keyframe_path=first_frame_path,
                clip_index=clip_index,
            )

        video = operation.response.generated_videos[0]

        # Save video
        video_id = str(uuid.uuid4())[:8]
        video_filename = f"interp_{clip_index + 1}_{video_id}.mp4"
        video_path = self.output_dir / video_filename

        self.client.files.download(file=video.video)
        video.video.save(str(video_path))

        logger.info(f"[VideoGenerator] Interpolation clip saved: {video_filename} (8s)")

        return VideoClipResult(
            video_path=video_path,
            duration_seconds=8,
            keyframe_path=first_frame_path,
            clip_index=clip_index,
        )

    async def generate_minimal_motion_clip(
        self,
        image_path: Path,
        duration_seconds: int = 4,
        clip_index: int = 0,
    ) -> VideoClipResult:
        """
        Generate a short clip with minimal motion (no last_frame constraint).

        Uses pure image-to-video which allows 4/6/8s durations.
        Best for quick, stable animations that feel like camera cuts.

        Args:
            image_path: Panel image to animate
            duration_seconds: 4, 6, or 8 seconds (default 4)
            clip_index: Index for logging/naming

        Returns:
            VideoClipResult with video path
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        logger.info(f"[VideoGenerator] Generating {duration_seconds}s minimal motion clip {clip_index + 1}: {image_path.name}")

        image = types.Image.from_file(location=str(image_path))

        # Minimal prompt for subtle, stable animation
        prompt = """Animate with very subtle, minimal motion only.

ONLY add:
- Gentle breathing (slight chest movement)
- 1-2 soft eye blinks
- Tiny hair/fur sway

DO NOT:
- Move characters
- Change poses
- Add dramatic motion
- Change the scene

Keep it almost still, like a living photograph.
AUDIO: Soft ambient sounds. NO speech, NO music."""

        def start_veo_operation():
            """Start Veo image-to-video (no last_frame = flexible duration)."""
            return self.client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                image=image,
                config=types.GenerateVideosConfig(
                    aspect_ratio="9:16",
                    duration_seconds=duration_seconds,
                    # NO last_frame = can use 4/6/8s
                ),
            )

        def poll_operation(operation):
            """Poll until operation completes."""
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > VEO_MAX_WAIT_SECONDS:
                    raise TimeoutError(f"Veo generation timed out after {VEO_MAX_WAIT_SECONDS}s")

                logger.info(f"[VideoGenerator] Waiting for clip {clip_index + 1}... ({elapsed:.0f}s)")
                time.sleep(VEO_POLL_INTERVAL_SECONDS)
                operation = self.client.operations.get(operation)

            return operation

        try:
            operation = await asyncio.to_thread(start_veo_operation)
            logger.info(f"[VideoGenerator] Veo minimal motion started for clip {clip_index + 1}")

            operation = await asyncio.to_thread(poll_operation, operation)
            logger.info(f"[VideoGenerator] Minimal motion clip {clip_index + 1} complete")

        except Exception as e:
            logger.error(f"[VideoGenerator] Veo minimal motion error: {e}")
            return VideoClipResult(
                video_path=None,
                duration_seconds=duration_seconds,
                keyframe_path=image_path,
                clip_index=clip_index,
            )

        if not operation.response or not operation.response.generated_videos:
            logger.error("[VideoGenerator] Veo minimal motion failed - no video in response")
            return VideoClipResult(
                video_path=None,
                duration_seconds=duration_seconds,
                keyframe_path=image_path,
                clip_index=clip_index,
            )

        video = operation.response.generated_videos[0]

        # Save video
        video_id = str(uuid.uuid4())[:8]
        video_filename = f"min_{clip_index + 1}_{video_id}.mp4"
        video_path = self.output_dir / video_filename

        self.client.files.download(file=video.video)
        video.video.save(str(video_path))

        logger.info(f"[VideoGenerator] Minimal motion clip saved: {video_filename} ({duration_seconds}s)")

        return VideoClipResult(
            video_path=video_path,
            duration_seconds=duration_seconds,
            keyframe_path=image_path,
            clip_index=clip_index,
        )

    async def generate_living_image_clip(
        self,
        image_path: Path,
        story_beat: str = None,
        clip_index: int = 0,
    ) -> VideoClipResult:
        """
        Generate a "living image" clip - same image as start AND end frame.

        This creates subtle animation (breathing, blinking, hair sway) without
        any morphing or composition changes. Much more reliable than interpolation.
        NOTE: Requires 8s duration due to last_frame constraint.

        Args:
            image_path: Panel image to animate
            story_beat: Optional context (mostly ignored, kept minimal)
            clip_index: Index for logging/naming

        Returns:
            VideoClipResult with video path (8s duration)
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        logger.info(f"[VideoGenerator] Generating living image clip {clip_index + 1}: {image_path.name}")

        # Load same image for both start and end
        image = types.Image.from_file(location=str(image_path))

        # Use minimal prompt - don't over-engineer
        prompt = self._build_living_image_prompt(story_beat)

        logger.debug(f"[VideoGenerator] Living image prompt:\n{prompt}")

        def start_veo_operation():
            """Start Veo with same image as start+end."""
            return self.client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                image=image,
                config=types.GenerateVideosConfig(
                    aspect_ratio="9:16",
                    last_frame=image,  # SAME image = no morphing, but requires 8s
                ),
            )

        def poll_operation(operation):
            """Poll until operation completes."""
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > VEO_MAX_WAIT_SECONDS:
                    raise TimeoutError(f"Veo generation timed out after {VEO_MAX_WAIT_SECONDS}s")

                logger.info(f"[VideoGenerator] Waiting for living image clip {clip_index + 1}... ({elapsed:.0f}s)")
                time.sleep(VEO_POLL_INTERVAL_SECONDS)
                operation = self.client.operations.get(operation)

            return operation

        try:
            operation = await asyncio.to_thread(start_veo_operation)
            logger.info(f"[VideoGenerator] Veo living image started for clip {clip_index + 1}")

            operation = await asyncio.to_thread(poll_operation, operation)
            logger.info(f"[VideoGenerator] Living image clip {clip_index + 1} complete")

        except Exception as e:
            logger.error(f"[VideoGenerator] Veo living image error: {e}")
            return VideoClipResult(
                video_path=None,
                duration_seconds=8,
                keyframe_path=image_path,
                clip_index=clip_index,
            )

        if not operation.response or not operation.response.generated_videos:
            logger.error("[VideoGenerator] Veo living image failed - no video in response")
            return VideoClipResult(
                video_path=None,
                duration_seconds=8,
                keyframe_path=image_path,
                clip_index=clip_index,
            )

        video = operation.response.generated_videos[0]

        # Save video
        video_id = str(uuid.uuid4())[:8]
        video_filename = f"living_{clip_index + 1}_{video_id}.mp4"
        video_path = self.output_dir / video_filename

        self.client.files.download(file=video.video)
        video.video.save(str(video_path))

        logger.info(f"[VideoGenerator] Living image clip saved: {video_filename} (8s)")

        return VideoClipResult(
            video_path=video_path,
            duration_seconds=8,
            keyframe_path=image_path,
            clip_index=clip_index,
        )

    # Legacy methods for backwards compatibility
    async def _generate_text_to_video(self, prompt: str, output_path: Path, context: str = "video") -> Path:
        """
        Internal helper for text-to-video generation using Veo async operations.

        Args:
            prompt: Text description of video to generate
            output_path: Where to save the generated video
            context: Description for logging

        Returns:
            Path to saved video file
        """
        logger.info(f"[VideoGenerator] Generating {context}...")

        def start_veo_operation():
            return self.client.models.generate_videos(
                model=self.model,
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio="9:16",  # Vertical for phone/manga
                ),
            )

        def poll_operation(operation):
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > VEO_MAX_WAIT_SECONDS:
                    raise TimeoutError(f"Veo generation timed out after {VEO_MAX_WAIT_SECONDS}s")

                logger.info(f"[VideoGenerator] Waiting for {context}... ({elapsed:.0f}s)")
                time.sleep(VEO_POLL_INTERVAL_SECONDS)
                operation = self.client.operations.get(operation)

            return operation

        try:
            operation = await asyncio.to_thread(start_veo_operation)
            operation = await asyncio.to_thread(poll_operation, operation)
        except Exception as e:
            logger.error(f"[VideoGenerator] Veo API error: {e}")
            raise

        if not operation.response or not operation.response.generated_videos:
            raise RuntimeError(f"{context} generation failed - no video in response")

        video = operation.response.generated_videos[0]

        # Download and save
        self.client.files.download(file=video.video)
        video.video.save(str(output_path))

        logger.info(f"[VideoGenerator] {context} saved: {output_path}")
        return output_path

    async def generate_scene(
        self,
        characters: list[Character],
        world: World,
        scene_concept: dict,
        duration: int = VIDEO_DURATION_SECONDS,
    ) -> Path:
        """
        Generate a video scene (legacy method).

        For new code, prefer generate_clip_from_keyframe with manga panels.
        """
        # Build character descriptions
        char_descriptions = "\n".join([
            f"- {c.name}: {c.visual_description}"
            for c in characters
        ])

        # Build generation prompt
        prompt = Prompts.GENERATE_SCENE_PROMPT.format(
            world_description=world.to_prompt_context(),
            character_descriptions=char_descriptions,
            scene_description=scene_concept.get("scene_description", ""),
            camera_movement=scene_concept.get("suggested_camera_movement", "slow pan"),
            duration=duration,
            mood=scene_concept.get("emotional_arc", "adventurous"),
        )

        scene_id = scene_concept.get("scene_title", "scene").replace(" ", "_").lower()
        output_path = self.output_dir / f"{scene_id}.mp4"

        return await self._generate_text_to_video(
            prompt=prompt,
            output_path=output_path,
            context=f"scene: {scene_concept.get('scene_title', 'Untitled')}",
        )

    async def generate_character_intro(
        self,
        character: Character,
        duration: int = 5,
    ) -> Path:
        """Generate a short intro video for a character."""
        prompt = f"""Create a character introduction video:

Character: {character.name}
Visual: {character.visual_description}
Personality: {character.personality_summary}

The video should:
- Start with character silhouette or partial view
- Reveal the full character with a confident pose
- Show 1-2 signature expressions
- Style: {character.style}
- Duration: {duration} seconds
- Mood: Exciting reveal, heroic introduction"""

        output_path = self.output_dir / f"intro_{character.id}.mp4"

        return await self._generate_text_to_video(
            prompt=prompt,
            output_path=output_path,
            context=f"intro for {character.name}",
        )

    async def evaluate_clip(
        self,
        video_path: Path,
        panel_path: Path,
        character_sheets: list[Path] = None,
        expected_audio: str = "animal_sounds",  # "animal_sounds" or "speech"
        clip_index: int = 0,
    ) -> dict:
        """
        Evaluate generated video against references using Gemini 3 Pro.

        Sends video + reference images to Gemini for quality assessment.
        Results are logged only (not used for retry decisions).

        Args:
            video_path: Path to generated video clip
            panel_path: Original manga panel for comparison
            character_sheets: Character reference images
            expected_audio: What audio type was requested
            clip_index: Clip number for logging

        Returns:
            Evaluation dict with scores and suggestions
        """
        from config import GEMINI_PRO_MODEL

        if not video_path or not video_path.exists():
            return {"error": "Video file not found", "overall_score": 0}

        logger.info(f"[VideoGenerator] Evaluating clip {clip_index + 1}...")

        try:
            # Upload video to Gemini Files API
            video_file = self.client.files.upload(file=str(video_path))

            # Wait for video processing
            import time
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = self.client.files.get(name=video_file.name)

            if video_file.state.name != "ACTIVE":
                return {"error": f"Video processing failed: {video_file.state.name}", "overall_score": 0}

            # Build evaluation prompt
            eval_prompt = f"""Evaluate this generated anime video clip against the reference images.

EXPECTED AUDIO TYPE: {expected_audio}
- If "animal_sounds": character should make animal vocalizations, NOT human speech
- If "speech": character should speak naturally

Rate each criterion from 0-10 and provide specific feedback.

EVALUATION CRITERIA:

1. CHARACTER CONSISTENCY (0-10)
   Does the animated character match the character reference sheet?
   - Check: proportions, colors, outfit, distinctive features
   - Deduct points for: wrong colors, missing features, proportion errors

2. SCENE ACCURACY (0-10)
   Does the animation match the panel composition?
   - Check: pose, framing, background elements, lighting
   - Deduct points for: wrong pose, missing elements, incorrect framing

3. AUDIO QUALITY (0-10)
   Is the audio appropriate for the expected type?
   - For animal_sounds: Are there animal vocalizations? No human speech?
   - For speech: Is dialogue clear and emotional?
   - Check: No unwanted background music

4. MOTION QUALITY (0-10)
   Is the animation smooth and natural?
   - Check: fluid movement, no jarring cuts, appropriate pacing
   - Deduct points for: glitches, unnatural motion, frozen frames

Respond in JSON format:
{{
    "overall_score": <average of all scores>,
    "character_consistency": <0-10>,
    "scene_accuracy": <0-10>,
    "audio_quality": <0-10>,
    "motion_quality": <0-10>,
    "issues": ["issue 1", "issue 2"],
    "suggestions": ["suggestion 1", "suggestion 2"]
}}"""

            # Build content with video and references
            content_parts = [video_file]

            # Add panel reference
            if panel_path and panel_path.exists():
                with open(panel_path, 'rb') as f:
                    panel_data = f.read()
                mime = 'image/png' if str(panel_path).endswith('.png') else 'image/jpeg'
                panel_image = types.Part.from_bytes(data=panel_data, mime_type=mime)
                content_parts.append(types.Part.from_text(text="Reference panel (target composition):"))
                content_parts.append(panel_image)

            # Add character sheets
            if character_sheets:
                for i, sheet_path in enumerate(character_sheets[:2]):
                    if sheet_path and sheet_path.exists():
                        with open(sheet_path, 'rb') as f:
                            sheet_data = f.read()
                        mime = 'image/png' if str(sheet_path).endswith('.png') else 'image/jpeg'
                        sheet_image = types.Part.from_bytes(data=sheet_data, mime_type=mime)
                        content_parts.append(types.Part.from_text(text=f"Character sheet {i+1}:"))
                        content_parts.append(sheet_image)

            content_parts.append(types.Part.from_text(text=eval_prompt))

            # Call Gemini Pro for evaluation
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=GEMINI_PRO_MODEL,
                contents=content_parts,
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Low temp for consistent evaluation
                ),
            )

            # Parse JSON response
            import json
            response_text = response.text.strip()
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            evaluation = json.loads(response_text)

            # Log results
            logger.info(f"[VideoGenerator] Clip {clip_index + 1} evaluation:")
            logger.info(f"  Overall score: {evaluation.get('overall_score', 'N/A')}/10")
            logger.info(f"  Character consistency: {evaluation.get('character_consistency', 'N/A')}/10")
            logger.info(f"  Scene accuracy: {evaluation.get('scene_accuracy', 'N/A')}/10")
            logger.info(f"  Audio quality: {evaluation.get('audio_quality', 'N/A')}/10")
            logger.info(f"  Motion quality: {evaluation.get('motion_quality', 'N/A')}/10")
            if evaluation.get('issues'):
                logger.info(f"  Issues: {evaluation['issues']}")
            if evaluation.get('suggestions'):
                logger.info(f"  Suggestions: {evaluation['suggestions']}")

            # Clean up uploaded video file
            try:
                self.client.files.delete(name=video_file.name)
            except Exception:
                pass  # Ignore cleanup errors

            return evaluation

        except Exception as e:
            logger.error(f"[VideoGenerator] Evaluation error for clip {clip_index + 1}: {e}")
            return {"error": str(e), "overall_score": 0}
