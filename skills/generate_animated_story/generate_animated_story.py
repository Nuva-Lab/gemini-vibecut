"""
Animated Story Generation - Veo 3.1 Minimal Motion Pipeline.

Supports two audio modes:
A) Dialogue mode: Qwen3-TTS → word alignment → karaoke captions
B) Music mode: ElevenLabs → panel-locked lyrics → rolling captions

4s mode is ideal because:
- Shorter = more stable (less time to drift)
- Feels like quick camera cuts in a film
- 4 panels × 4s = 16s total (snappy pacing)
"""

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Optional

from skills.generate_manga.generate_manga import MangaResult, MangaPanel
from skills.generate_video.generate_video import VideoGenerator, VideoClipResult
from skills.compose_final.compose_final import VideoComposer
from skills.verify_output import verify_video
from config import OUTPUT_DIR

# Lazy imports for TTS/alignment (these have heavy dependencies)
# from skills.qwen_tts import QwenTTS, TTSResult
# from skills.align_captions import CaptionAligner, AlignedCaption
# from skills.render_captions import CaptionRenderer, CaptionSegment, WordSegment

logger = logging.getLogger(__name__)


@dataclass
class DialogueLine:
    """Parsed dialogue line with speaker and text."""
    speaker: str
    text: str
    panel_index: int


@dataclass
class AnimatedStoryResult:
    """Result of animated story generation."""
    story_id: str
    final_video_path: Path
    total_duration: float
    clip_count: int
    video_paths: list[Path]


@dataclass
class AnimationStreamEvent:
    """Event emitted during streaming animation generation."""
    type: str  # 'start', 'video_progress', 'compose', 'complete', 'error'
    data: dict = field(default_factory=dict)


class AnimatedStoryGenerator:
    """
    Generate animated story from manga panels using Veo 3.1 minimal motion mode.

    Full pipeline with dialogue:
    1. Parse dialogue from panels → speaker + text
    2. Generate TTS audio per panel (Qwen3-TTS)
    3. Align audio → word timestamps (Qwen3-ForcedAligner)
    4. Generate video clips (Veo 3.1, 4s each)
    5. Merge audio + video per clip
    6. Render karaoke captions (Remotion)
    7. Concatenate into final video

    For N panels, generates N clips (each 4 seconds).
    Total duration: 4 panels × 4s = 16s.
    """

    def __init__(
        self,
        video_generator: VideoGenerator = None,
        composer: VideoComposer = None,
    ):
        """Initialize with video generator and composer."""
        self.video = video_generator or VideoGenerator()
        self.composer = composer or VideoComposer()
        self.output_dir = OUTPUT_DIR / "animated_stories"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Lazy-loaded components
        self._tts = None
        self._aligner = None
        self._renderer = None

    def _get_tts(self, mode: str = "auto"):
        """Lazy-load TTS generator."""
        if self._tts is None or getattr(self._tts, 'mode', None) != mode:
            from skills.qwen_tts import QwenTTS
            self._tts = QwenTTS(output_dir=self.output_dir / "audio", mode=mode)
        return self._tts

    def _get_aligner(self):
        """Lazy-load caption aligner."""
        if self._aligner is None:
            from skills.align_captions import CaptionAligner
            self._aligner = CaptionAligner(device="cpu")
        return self._aligner

    def _get_renderer(self):
        """Lazy-load caption renderer."""
        if self._renderer is None:
            from skills.render_captions import CaptionRenderer
            self._renderer = CaptionRenderer(output_dir=self.output_dir / "rendered")
        return self._renderer

    def _parse_dialogue(self, dialogue: str, panel_index: int) -> Optional[DialogueLine]:
        """
        Parse dialogue string into speaker and text.

        Formats supported:
        - "Character: Text here"
        - "Text here" (no speaker)
        """
        if not dialogue or not dialogue.strip():
            return None

        dialogue = dialogue.strip()

        # Try to match "Speaker: Text" pattern
        match = re.match(r'^([^:]+):\s*(.+)$', dialogue)
        if match:
            return DialogueLine(
                speaker=match.group(1).strip(),
                text=match.group(2).strip(),
                panel_index=panel_index,
            )

        # No speaker prefix, return as-is
        return DialogueLine(
            speaker="",
            text=dialogue,
            panel_index=panel_index,
        )

    def _get_panel_image_path(self, panel: MangaPanel) -> Optional[Path]:
        """Get the actual file path for a manga panel image."""
        # Try image_path first
        if panel.image_path and panel.image_path.exists():
            return panel.image_path

        # Try to resolve from image_url
        if panel.image_url:
            # image_url is like "/assets/outputs/manga/abc_panel_1.png"
            url_path = panel.image_url.lstrip('/')
            resolved = OUTPUT_DIR.parent / url_path
            if resolved.exists():
                return resolved

            # Try direct from OUTPUT_DIR
            manga_dir = OUTPUT_DIR / "manga"
            filename = Path(panel.image_url).name
            direct_path = manga_dir / filename
            if direct_path.exists():
                return direct_path

        return None

    async def generate_animated_story_streaming(
        self,
        manga_result: MangaResult,
        characters: list[dict] = None,
        character_sheets: dict[str, Path] = None,
        music_path: Path = None,
        clip_duration: int = 4,
    ) -> AsyncGenerator[AnimationStreamEvent, None]:
        """
        Generate animated story with streaming progress updates.

        Uses Veo 3.1 minimal motion mode - 4s clips with subtle animation.
        Short duration keeps clips stable with camera-cut feel.

        Args:
            manga_result: Output from MangaGenerator
            characters: Character data (for logging)
            character_sheets: Not used in minimal motion mode
            music_path: Optional background music (added after)
            clip_duration: Duration per clip (4, 6, or 8 seconds, default 4)

        Yields:
            AnimationStreamEvent objects for progress tracking
        """
        story_id = manga_result.manga_id or str(uuid.uuid4())[:8]
        panels = manga_result.panels
        characters = characters or []

        if not panels:
            yield AnimationStreamEvent('error', {'message': 'No panels in manga result'})
            return

        # N panels = N clips (each panel becomes an animated clip)
        clip_count = len(panels)

        # Start event
        yield AnimationStreamEvent('start', {
            'story_id': story_id,
            'panel_count': len(panels),
            'clip_count': clip_count,
            'clip_duration': clip_duration,
            'total_duration': clip_count * clip_duration,
            'mode': 'minimal_motion',
        })
        await asyncio.sleep(0)

        # Step 1: Collect all panel paths
        panel_paths = []
        for panel in panels:
            path = self._get_panel_image_path(panel)
            panel_paths.append(path)

        valid_count = sum(1 for p in panel_paths if p)
        logger.info(f"[AnimatedStory] Collected {valid_count}/{len(panels)} panel paths ({clip_duration}s minimal motion mode)")

        if valid_count == 0:
            yield AnimationStreamEvent('error', {'message': 'No valid panel images found'})
            return

        # Step 2: Generate living image clips (one per panel)
        clips: list[tuple[Path, float]] = []
        clips_failed = 0

        for i, panel in enumerate(panels):
            panel_path = panel_paths[i]

            yield AnimationStreamEvent('video_progress', {
                'clip_index': i + 1,
                'total': clip_count,
                'message': f'Animating panel {i + 1}/{clip_count}...'
            })
            await asyncio.sleep(0)

            if not panel_path:
                logger.warning(f"[AnimatedStory] Missing panel path for clip {i + 1}, skipping")
                clips_failed += 1
                continue

            # Retry logic
            max_attempts = 3
            video_result = None

            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        logger.info(f"[AnimatedStory] Retry {attempt}/{max_attempts-1} for clip {i + 1}")
                        yield AnimationStreamEvent('video_progress', {
                            'clip_index': i + 1,
                            'total': clip_count,
                            'message': f'Retrying panel {i + 1}/{clip_count} (attempt {attempt + 1}/{max_attempts})...'
                        })
                        await asyncio.sleep(2)

                    # Generate minimal motion clip (4s, stable)
                    video_result = await self.video.generate_minimal_motion_clip(
                        image_path=panel_path,
                        duration_seconds=clip_duration,
                        clip_index=i,
                    )

                    if video_result.video_path is not None:
                        break
                    else:
                        logger.warning(f"[AnimatedStory] Clip {i + 1} attempt {attempt + 1} returned no video")

                except Exception as e:
                    logger.error(f"[AnimatedStory] Error clip {i + 1} attempt {attempt + 1}: {e}")

            if video_result is None or video_result.video_path is None:
                logger.error(f"[AnimatedStory] Clip {i + 1} failed after {max_attempts} attempts")
                clips_failed += 1
                continue

            clips.append((video_result.video_path, video_result.duration_seconds))
            logger.info(f"[AnimatedStory] Clip {i + 1}: {video_result.video_path} ({video_result.duration_seconds}s)")

            yield AnimationStreamEvent('video_progress', {
                'clip_index': i + 1,
                'total': clip_count,
                'message': f'Panel {i + 1}/{clip_count} animated ({clip_duration}s)'
            })

        # Step 3: Concatenate clips
        yield AnimationStreamEvent('compose', {
            'message': 'Composing final video...'
        })
        await asyncio.sleep(0)

        if not clips:
            yield AnimationStreamEvent('error', {
                'message': 'No video clips generated successfully'
            })
            return

        try:
            clip_paths = [clip for clip, _ in clips]
            total_duration = sum(dur for _, dur in clips)

            # Concatenate all clips
            final_path = await self.composer.concatenate_scenes(
                scene_paths=clip_paths,
                output_name=f"story_{story_id}_final",
            )

            # Add background music if provided
            if music_path and music_path.exists():
                final_path = await self.composer.compose_video_with_music(
                    video_path=final_path,
                    music_path=music_path,
                    output_name=f"story_{story_id}_with_music",
                    music_volume=0.5,
                )

            # Verify output
            verification = verify_video(
                path=final_path,
                expected_duration=total_duration,
                expected_width=1080,
                expected_height=1920,
                duration_tolerance=2.0,
            )

            # Auto-retry with forced normalization on resolution mismatch
            if not verification.passed and any("Resolution" in f for f in verification.failures):
                logger.warning("[AnimatedStory] Verification failed (resolution), retrying with normalization")
                final_path = await self.composer.concatenate_scenes(
                    scene_paths=clip_paths,
                    output_name=f"story_{story_id}_final_norm",
                    target_width=1080,
                    target_height=1920,
                )
                verification = verify_video(
                    path=final_path,
                    expected_duration=total_duration,
                    expected_width=1080,
                    expected_height=1920,
                    duration_tolerance=2.0,
                )

            # Convert to URL for browser (supports session-scoped paths)
            try:
                assets_root = Path(__file__).parent.parent.parent / "assets"
                rel_path = final_path.resolve().relative_to(assets_root.resolve())
                final_url = f"/assets/{rel_path}"
            except ValueError:
                final_url = f"/assets/outputs/final/{final_path.name}"

            yield AnimationStreamEvent('complete', {
                'story_id': story_id,
                'final_video_path': final_url,
                'total_duration': round(total_duration, 2),
                'clip_count': len(clips),
                'clips_attempted': clip_count,
                'clips_failed': clips_failed,
                'verified': verification.passed,
                'actual_duration': round(verification.actual_duration, 2),
                'actual_resolution': f"{verification.actual_width}x{verification.actual_height}",
                'verification_failures': verification.failures if not verification.passed else [],
            })

            logger.info(f"[AnimatedStory] Complete: {final_path} ({total_duration:.1f}s, {len(clips)} clips, verified={verification.passed})")

        except Exception as e:
            logger.error(f"[AnimatedStory] Composition error: {e}")
            yield AnimationStreamEvent('error', {
                'message': f'Composition failed: {str(e)[:100]}'
            })

    async def generate_animated_story(
        self,
        manga_result: MangaResult,
        characters: list[dict] = None,
        character_sheets: dict[str, Path] = None,
        music_path: Path = None,
        clip_duration: int = 4,
    ) -> AnimatedStoryResult:
        """
        Generate animated story (non-streaming).

        For progress tracking, use generate_animated_story_streaming instead.

        Args:
            clip_duration: Duration per clip (4, 6, or 8 seconds, default 4)

        Returns:
            AnimatedStoryResult with final video path
        """
        result = AnimatedStoryResult(
            story_id="",
            final_video_path=None,
            total_duration=0.0,
            clip_count=0,
            video_paths=[],
        )

        async for event in self.generate_animated_story_streaming(
            manga_result=manga_result,
            characters=characters,
            character_sheets=character_sheets,
            music_path=music_path,
            clip_duration=clip_duration,
        ):
            if event.type == 'start':
                result.story_id = event.data['story_id']
            elif event.type == 'complete':
                result.final_video_path = Path(event.data['final_video_path'])
                result.total_duration = event.data['total_duration']
                result.clip_count = event.data['clip_count']
            elif event.type == 'error':
                raise RuntimeError(event.data['message'])

        return result

    async def generate_animated_story_with_dialogue_streaming(
        self,
        manga_result: MangaResult,
        characters: list[dict] = None,
        character_personas: dict[str, str] = None,
        character_voices: dict[str, str] = None,
        music_path: Path = None,
        clip_duration: int = 4,
        enable_captions: bool = True,
        language: str = "English",
        tts_mode: str = "auto",
    ) -> AsyncGenerator[AnimationStreamEvent, None]:
        """
        Generate animated story with TTS dialogue and karaoke captions.

        Full pipeline:
        1. Parse dialogue from panels
        2. Generate TTS audio per panel (local mlx_audio or cloud FAL)
        3. Align audio to get word timestamps
        4. Generate video clips (Veo 3.1)
        5. Merge audio + video per clip
        6. Render karaoke captions (Remotion)
        7. Concatenate into final video

        Args:
            manga_result: Output from MangaGenerator (with dialogue)
            characters: Character data with name and persona
            character_personas: Persona instructions for voice design (local mode)
                e.g. {"Mochi": "A cheerful young girl", "Hero": "A brave young man"}
            character_voices: Predefined voice names (cloud mode)
                Available: Vivian, Serena, Dylan, Eric, Ryan, Aiden, Ono_Anna, Sohee, Uncle_Fu
            music_path: Optional background music
            clip_duration: Duration per clip (4, 6, or 8 seconds)
            enable_captions: Whether to render karaoke captions
            language: Language for alignment ('English' or 'Chinese')
            tts_mode: TTS mode ('local', 'cloud', or 'auto')

        Yields:
            AnimationStreamEvent objects for progress tracking
        """
        story_id = manga_result.manga_id or str(uuid.uuid4())[:8]
        panels = manga_result.panels
        characters = characters or []
        character_voices = character_voices or {}

        # Build character personas from characters list if not provided
        if character_personas is None:
            character_personas = {}
            for char in characters:
                name = char.get("name", "")
                persona = char.get("persona", "")
                if name and persona:
                    # Convert persona to voice description
                    character_personas[name] = f"A character who is {persona}"

        if not panels:
            yield AnimationStreamEvent('error', {'message': 'No panels in manga result'})
            return

        clip_count = len(panels)

        # Start event
        yield AnimationStreamEvent('start', {
            'story_id': story_id,
            'panel_count': len(panels),
            'clip_count': clip_count,
            'clip_duration': clip_duration,
            'total_duration': clip_count * clip_duration,
            'mode': 'dialogue_with_captions',
        })
        await asyncio.sleep(0)

        # Step 1: Collect panel paths and parse dialogues
        panel_paths = []
        dialogues = []
        for i, panel in enumerate(panels):
            path = self._get_panel_image_path(panel)
            panel_paths.append(path)
            dialogue = self._parse_dialogue(panel.dialogue, i)
            dialogues.append(dialogue)

        valid_count = sum(1 for p in panel_paths if p)
        dialogue_count = sum(1 for d in dialogues if d)
        logger.info(f"[AnimatedStory] {valid_count}/{len(panels)} panels, {dialogue_count} with dialogue")

        if valid_count == 0:
            yield AnimationStreamEvent('error', {'message': 'No valid panel images found'})
            return

        # Step 2: Generate TTS for each panel with dialogue
        yield AnimationStreamEvent('tts_progress', {
            'message': f'Generating dialogue audio ({dialogue_count} lines)...'
        })
        await asyncio.sleep(0)

        tts = self._get_tts(mode=tts_mode)
        audio_results: list[tuple[Path, float, Optional[DialogueLine]]] = []

        # Collect dialogue lines for batch generation
        dialogue_lines_for_tts = []
        dialogue_index_map = []  # Maps TTS result index -> panel index
        for i, dialogue in enumerate(dialogues):
            if dialogue:
                dialogue_lines_for_tts.append((dialogue.speaker, dialogue.text))
                dialogue_index_map.append(i)

        if dialogue_lines_for_tts:
            try:
                # In torch mode, generate_dialogue auto-initializes character
                # voices from personas (VoiceDesign → Clone pattern) and uses
                # cached clone prompts for consistent timbre across all lines.
                tts_results = await tts.generate_dialogue(
                    dialogue_lines=dialogue_lines_for_tts,
                    character_personas=character_personas,
                    character_voices=character_voices,
                    output_dir=self.output_dir / "audio",
                    language=language,
                )
            except Exception as e:
                logger.error(f"[AnimatedStory] TTS batch error: {e}")
                tts_results = [None] * len(dialogue_lines_for_tts)

            # Map TTS results back to panel indices
            tts_result_map = {}
            for idx, panel_i in enumerate(dialogue_index_map):
                tts_result_map[panel_i] = tts_results[idx] if idx < len(tts_results) else None

            for i, dialogue in enumerate(dialogues):
                tts_result = tts_result_map.get(i)
                if dialogue and tts_result:
                    audio_results.append((tts_result.audio_path, tts_result.duration_seconds, dialogue))
                    logger.info(f"[AnimatedStory] TTS panel {i+1}: {tts_result.duration_seconds:.2f}s")
                elif dialogue:
                    logger.error(f"[AnimatedStory] TTS failed for panel {i+1}")
                    audio_results.append((None, 0.0, dialogue))
                else:
                    audio_results.append((None, 0.0, None))

                yield AnimationStreamEvent('tts_progress', {
                    'panel_index': i + 1,
                    'total': clip_count,
                    'message': f'Audio {i+1}/{clip_count} generated' if dialogue and tts_result_map.get(i) else f'Panel {i+1} (no dialogue)'
                })
        else:
            # No dialogue at all
            for i in range(len(dialogues)):
                audio_results.append((None, 0.0, None))

        # Step 3: Align audio to get word timestamps (if captions enabled)
        aligned_captions = []
        if enable_captions:
            yield AnimationStreamEvent('align_progress', {
                'message': 'Aligning dialogue for karaoke captions...'
            })
            await asyncio.sleep(0)

            aligner = self._get_aligner()
            for i, (audio_path, duration, dialogue) in enumerate(audio_results):
                if audio_path and dialogue:
                    try:
                        captions = await aligner.align_audio(
                            audio_path=audio_path,
                            text=dialogue.text,
                            language=language,
                            phrase_level=False,  # Word-level for karaoke
                        )
                        aligned_captions.append((captions, dialogue.speaker))
                        logger.info(f"[AnimatedStory] Aligned panel {i+1}: {len(captions)} segments")
                    except Exception as e:
                        logger.error(f"[AnimatedStory] Alignment error panel {i+1}: {e}")
                        aligned_captions.append(([], dialogue.speaker if dialogue else ""))
                else:
                    aligned_captions.append(([], ""))

        # Step 4: Generate video clips (Veo 3.1)
        clips: list[tuple[Path, float]] = []
        clips_failed = 0

        for i, panel in enumerate(panels):
            panel_path = panel_paths[i]

            yield AnimationStreamEvent('video_progress', {
                'clip_index': i + 1,
                'total': clip_count,
                'message': f'Animating panel {i + 1}/{clip_count}...'
            })
            await asyncio.sleep(0)

            if not panel_path:
                logger.warning(f"[AnimatedStory] Missing panel path for clip {i + 1}")
                clips_failed += 1
                clips.append((None, clip_duration))
                continue

            max_attempts = 3
            video_result = None

            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        await asyncio.sleep(2)

                    video_result = await self.video.generate_minimal_motion_clip(
                        image_path=panel_path,
                        duration_seconds=clip_duration,
                        clip_index=i,
                    )

                    if video_result.video_path is not None:
                        break

                except Exception as e:
                    logger.error(f"[AnimatedStory] Video error clip {i + 1} attempt {attempt + 1}: {e}")

            if video_result is None or video_result.video_path is None:
                logger.error(f"[AnimatedStory] Clip {i + 1} failed")
                clips_failed += 1
                clips.append((None, clip_duration))
                continue

            clips.append((video_result.video_path, video_result.duration_seconds))
            logger.info(f"[AnimatedStory] Clip {i + 1}: {video_result.video_path}")

            yield AnimationStreamEvent('video_progress', {
                'clip_index': i + 1,
                'total': clip_count,
                'message': f'Panel {i + 1}/{clip_count} animated'
            })

        # Step 5: Merge audio + video per clip
        yield AnimationStreamEvent('compose', {
            'message': 'Merging audio with video clips...'
        })
        await asyncio.sleep(0)

        merged_clips = []
        for i, ((video_path, video_dur), (audio_path, audio_dur, _)) in enumerate(zip(clips, audio_results)):
            if video_path is None:
                merged_clips.append(None)
                continue

            if audio_path:
                try:
                    merged_path = await self.composer.add_audio_to_clip(
                        video_path=video_path,
                        audio_path=audio_path,
                        video_duration=video_dur,
                        output_name=f"story_{story_id}_clip_{i}_merged",
                    )
                    merged_clips.append(merged_path)
                except Exception as e:
                    logger.error(f"[AnimatedStory] Merge error clip {i + 1}: {e}")
                    merged_clips.append(video_path)  # Use silent video
            else:
                merged_clips.append(video_path)  # No audio for this clip

        # Step 6: Render with captions (if enabled and Remotion available)
        final_clips = merged_clips
        if enable_captions and aligned_captions:
            try:
                yield AnimationStreamEvent('caption_progress', {
                    'message': 'Rendering karaoke captions...'
                })
                await asyncio.sleep(0)

                renderer = self._get_renderer()
                from skills.render_captions import CaptionSegment, WordSegment

                captioned_clips = []
                for i, (clip_path, (captions, speaker)) in enumerate(zip(merged_clips, aligned_captions)):
                    if clip_path is None:
                        captioned_clips.append(None)
                        continue

                    if captions:
                        # Convert AlignedCaption to CaptionSegment
                        caption_segments = []
                        for caption in captions:
                            words = [
                                WordSegment(text=w.text, startMs=w.start_ms, endMs=w.end_ms)
                                for w in caption.words
                            ]
                            caption_segments.append(CaptionSegment(
                                text=caption.text,
                                startMs=caption.start_ms,
                                endMs=caption.end_ms,
                                speaker=speaker,
                                words=words,
                            ))

                        try:
                            captioned_path = await renderer.render_with_captions(
                                video_path=clip_path,
                                captions=caption_segments,
                                output_name=f"story_{story_id}_clip_{i}_captioned",
                            )
                            captioned_clips.append(captioned_path)
                        except Exception as e:
                            logger.warning(f"[AnimatedStory] Caption render failed clip {i+1}: {e}")
                            captioned_clips.append(clip_path)
                    else:
                        captioned_clips.append(clip_path)

                final_clips = captioned_clips
            except ImportError:
                logger.warning("[AnimatedStory] Remotion not available, skipping captions")
            except Exception as e:
                logger.warning(f"[AnimatedStory] Caption rendering failed: {e}")

        # Step 7: Concatenate clips
        yield AnimationStreamEvent('compose', {
            'message': 'Concatenating final video...'
        })
        await asyncio.sleep(0)

        valid_clips = [c for c in final_clips if c is not None]
        if not valid_clips:
            yield AnimationStreamEvent('error', {
                'message': 'No video clips generated successfully'
            })
            return

        try:
            total_duration = sum(dur for _, dur in clips if dur)

            final_path = await self.composer.concatenate_scenes(
                scene_paths=valid_clips,
                output_name=f"story_{story_id}_final",
            )

            # Add background music if provided
            if music_path and music_path.exists():
                final_path = await self.composer.compose_video_with_music(
                    video_path=final_path,
                    music_path=music_path,
                    output_name=f"story_{story_id}_with_music",
                    music_volume=0.3,
                )

            # Verify output
            verification = verify_video(
                path=final_path,
                expected_duration=total_duration,
                expected_width=1080,
                expected_height=1920,
                require_audio=dialogue_count > 0,
                duration_tolerance=2.0,
            )

            # Auto-retry with forced normalization on resolution mismatch
            if not verification.passed and any("Resolution" in f for f in verification.failures):
                logger.warning("[AnimatedStory] Verification failed (resolution), retrying with normalization")
                final_path = await self.composer.concatenate_scenes(
                    scene_paths=valid_clips,
                    output_name=f"story_{story_id}_final_norm",
                    target_width=1080,
                    target_height=1920,
                )
                if music_path and music_path.exists():
                    final_path = await self.composer.compose_video_with_music(
                        video_path=final_path,
                        music_path=music_path,
                        output_name=f"story_{story_id}_with_music_norm",
                        music_volume=0.3,
                    )
                verification = verify_video(
                    path=final_path,
                    expected_duration=total_duration,
                    expected_width=1080,
                    expected_height=1920,
                    require_audio=dialogue_count > 0,
                    duration_tolerance=2.0,
                )

            # Convert to URL for browser (supports session-scoped paths)
            try:
                assets_root = Path(__file__).parent.parent.parent / "assets"
                rel_path = final_path.resolve().relative_to(assets_root.resolve())
                final_url = f"/assets/{rel_path}"
            except ValueError:
                final_url = f"/assets/outputs/final/{final_path.name}"

            yield AnimationStreamEvent('complete', {
                'story_id': story_id,
                'final_video_path': final_url,
                'total_duration': round(total_duration, 2),
                'clip_count': len(valid_clips),
                'clips_attempted': clip_count,
                'clips_failed': clips_failed,
                'has_dialogue': dialogue_count > 0,
                'has_captions': enable_captions and bool(aligned_captions),
                'verified': verification.passed,
                'actual_duration': round(verification.actual_duration, 2),
                'actual_resolution': f"{verification.actual_width}x{verification.actual_height}",
                'verification_failures': verification.failures if not verification.passed else [],
            })

            logger.info(f"[AnimatedStory] Complete: {final_path} (verified={verification.passed})")

        except Exception as e:
            logger.error(f"[AnimatedStory] Final composition error: {e}")
            yield AnimationStreamEvent('error', {
                'message': f'Composition failed: {str(e)[:100]}'
            })

    async def generate_animated_story_with_dialogue(
        self,
        manga_result: MangaResult,
        characters: list[dict] = None,
        character_personas: dict[str, str] = None,
        character_voices: dict[str, str] = None,
        music_path: Path = None,
        clip_duration: int = 4,
        enable_captions: bool = True,
        language: str = "English",
        tts_mode: str = "auto",
    ) -> AnimatedStoryResult:
        """
        Generate animated story with dialogue (non-streaming).

        For progress tracking, use generate_animated_story_with_dialogue_streaming.

        Returns:
            AnimatedStoryResult with final video path
        """
        result = AnimatedStoryResult(
            story_id="",
            final_video_path=None,
            total_duration=0.0,
            clip_count=0,
            video_paths=[],
        )

        async for event in self.generate_animated_story_with_dialogue_streaming(
            manga_result=manga_result,
            characters=characters,
            character_personas=character_personas,
            character_voices=character_voices,
            music_path=music_path,
            clip_duration=clip_duration,
            enable_captions=enable_captions,
            language=language,
            tts_mode=tts_mode,
        ):
            if event.type == 'start':
                result.story_id = event.data['story_id']
            elif event.type == 'complete':
                result.final_video_path = Path(event.data['final_video_path'])
                result.total_duration = event.data['total_duration']
                result.clip_count = event.data['clip_count']
            elif event.type == 'error':
                raise RuntimeError(event.data['message'])

        return result

    # =========================================================================
    # Music Pipeline (ElevenLabs + Rolling Lyrics)
    # =========================================================================

    def _get_music_generator(self):
        """Lazy-load ElevenLabs music generator."""
        if not hasattr(self, '_music_gen') or self._music_gen is None:
            from skills.generate_music.elevenlabs_music import ElevenLabsMusicGenerator
            self._music_gen = ElevenLabsMusicGenerator(
                output_dir=self.output_dir / "music",
            )
            logger.info("[AnimatedStory] Using ElevenLabs music generator")
        return self._music_gen

    def _get_storyboard_planner(self):
        """Lazy-load storyboard planner (for lyrics generation)."""
        if not hasattr(self, '_planner') or self._planner is None:
            from skills.generate_animated_story.storyboard_planner import StoryboardPlanner
            self._planner = StoryboardPlanner()
        return self._planner

    @staticmethod
    def _extract_plain_lyrics(lyrics: str) -> str:
        """Strip [Verse]/[Chorus]/etc. structure tags, returning plain text for alignment."""
        import re
        lines = []
        for line in lyrics.splitlines():
            stripped = line.strip()
            if stripped and not re.match(r'^\[.*\]$', stripped):
                lines.append(stripped)
        return " ".join(lines)

    @staticmethod
    def _extract_lyrics_lines(lyrics: str) -> list[str]:
        """Extract individual lyrics lines, stripping structure tags."""
        import re
        lines = []
        for line in lyrics.splitlines():
            stripped = line.strip()
            if stripped and not re.match(r'^\[.*\]$', stripped):
                lines.append(stripped)
        return lines

    async def _generate_all_clips(
        self,
        panels: list[MangaPanel],
        panel_paths: list[Path],
        clip_duration: int,
        story_id: str,
    ) -> list[tuple[Optional[Path], float]]:
        """Generate all Veo clips sequentially. Returns list of (path, duration) tuples."""
        clips = []
        for i, panel in enumerate(panels):
            panel_path = panel_paths[i]
            if not panel_path:
                clips.append((None, clip_duration))
                continue

            max_attempts = 3
            video_result = None

            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        await asyncio.sleep(2)
                    video_result = await self.video.generate_minimal_motion_clip(
                        image_path=panel_path,
                        duration_seconds=clip_duration,
                        clip_index=i,
                    )
                    if video_result.video_path is not None:
                        break
                except Exception as e:
                    logger.error(f"[AnimatedStory] Video clip {i+1} attempt {attempt+1}: {e}")

            if video_result and video_result.video_path:
                clips.append((video_result.video_path, video_result.duration_seconds))
                logger.info(f"[AnimatedStory] Clip {i+1}: {video_result.video_path}")
            else:
                clips.append((None, clip_duration))
                logger.error(f"[AnimatedStory] Clip {i+1} failed after {max_attempts} attempts")

        return clips

    async def _generate_music_task(
        self,
        prompt: str,
        lyrics: str,
        duration: int,
        clip_duration: int = 4,
        vocal_style: str = "",
        negative_tags: str = "",
        bpm: int = 0,
        panel_local_styles: list = None,
    ):
        """Generate music via ElevenLabs."""
        music_gen = self._get_music_generator()
        return await music_gen.generate_music(
            prompt=prompt,
            lyrics=lyrics,
            duration=duration,
            clip_duration=clip_duration,
            vocal_style=vocal_style,
            negative_tags=negative_tags,
            bpm=bpm,
            panel_local_styles=panel_local_styles,
        )

    async def generate_animated_story_with_music_streaming(
        self,
        manga_result: MangaResult,
        characters: list[dict] = None,
        character_name: str = "",
        story_summary: str = "",
        clip_duration: int = 4,
        enable_lyrics: bool = True,
        custom_tags: str = None,
        custom_lyrics: str = None,
    ) -> AsyncGenerator[AnimationStreamEvent, None]:
        """
        Generate animated story with ElevenLabs background music and rolling lyrics.

        Pipeline:
        1. Generate lyrics + tags (Gemini) — or use custom overrides
        2. PARALLEL: Veo clips + ElevenLabs music
        3. Concat clips → 16s base video
        4. Add music audio to video
        5. Render panel-locked lyrics via Remotion
        6. Verify output

        Args:
            manga_result: Output from MangaGenerator
            characters: Character data (for logging)
            character_name: Main character name (for lyrics context)
            story_summary: Brief story description (for lyrics context)
            clip_duration: Duration per clip (4, 6, or 8 seconds)
            enable_lyrics: Whether to render rolling lyrics overlay
            custom_tags: Override music prompt (skip Gemini lyrics gen)
            custom_lyrics: Override lyrics text (skip Gemini lyrics gen)

        Yields:
            AnimationStreamEvent objects for progress tracking
        """
        story_id = manga_result.manga_id or str(uuid.uuid4())[:8]
        panels = manga_result.panels
        characters = characters or []

        if not panels:
            yield AnimationStreamEvent('error', {'message': 'No panels in manga result'})
            return

        clip_count = len(panels)
        total_expected_duration = clip_count * clip_duration

        # Start event
        yield AnimationStreamEvent('start', {
            'story_id': story_id,
            'panel_count': len(panels),
            'clip_count': clip_count,
            'clip_duration': clip_duration,
            'total_duration': total_expected_duration,
            'mode': 'music_with_lyrics',
        })
        await asyncio.sleep(0)

        # Step 1: Generate lyrics + tags (or use custom overrides)
        vocal_style = ""
        negative_tags = ""
        bpm = 0
        lyrics_result = None  # Store full result for panel_local_styles

        if custom_tags and custom_lyrics:
            tags = custom_tags
            lyrics = custom_lyrics
            mood = "custom"
            logger.info("[AnimatedStory] Using custom tags/lyrics")
        else:
            yield AnimationStreamEvent('lyrics_progress', {
                'message': 'Generating song lyrics (Pro model)...'
            })
            await asyncio.sleep(0)

            try:
                planner = self._get_storyboard_planner()
                lyrics_result = await planner.generate_lyrics_and_tags(
                    panels=panels,
                    character_name=character_name,
                    story_summary=story_summary,
                )
                tags = custom_tags or lyrics_result.tags
                lyrics = custom_lyrics or lyrics_result.lyrics
                mood = lyrics_result.mood
                vocal_style = lyrics_result.vocal_style
                negative_tags = lyrics_result.negative_tags
                bpm = lyrics_result.bpm
            except Exception as e:
                logger.error(f"[AnimatedStory] Lyrics generation failed: {e}")
                tags = "anime pop, female vocals, piano, gentle, full instrumentation from first beat, 110 BPM"
                lyrics = (
                    "[Verse 1]\nShining in the morning light\nSomething new is waiting here\n"
                    "[Verse 2]\nRunning side by side we go\nEvery step a little braver\n"
                    "[Chorus]\nWe can fly together now\nNothing gonna hold us down\n"
                    "[Outro]\nStars are shining just for us\nThis is where our story starts"
                )
                mood = "hopeful"

            # Validate lyrics line count: expect 2 lines per panel (couplet structure)
            lyrics_lines_check = self._extract_lyrics_lines(lyrics)
            expected_lines = clip_count * 2  # 2 lines per panel = 8 for 4 panels
            if len(lyrics_lines_check) != expected_lines:
                logger.warning(
                    f"[AnimatedStory] Lyrics lines ({len(lyrics_lines_check)}) != expected ({expected_lines}). "
                    f"Caption-to-panel alignment will use grouping."
                )
            else:
                logger.info(f"[AnimatedStory] Lyrics: {len(lyrics_lines_check)} lines for {clip_count} panels (2:1 couplet)")

            yield AnimationStreamEvent('lyrics_progress', {
                'message': f'Lyrics ready (mood: {mood})',
                'tags': tags,
                'lyrics': lyrics,
            })
            await asyncio.sleep(0)

        # Step 2: Collect panel paths
        panel_paths = []
        for panel in panels:
            path = self._get_panel_image_path(panel)
            panel_paths.append(path)

        valid_count = sum(1 for p in panel_paths if p)
        if valid_count == 0:
            yield AnimationStreamEvent('error', {'message': 'No valid panel images found'})
            return

        # Step 3: PARALLEL — Veo clips + music generation
        yield AnimationStreamEvent('video_progress', {
            'message': f'Starting parallel generation: {clip_count} clips + music...',
        })
        yield AnimationStreamEvent('music_progress', {
            'message': 'Starting music generation...',
        })
        await asyncio.sleep(0)

        # ElevenLabs: duration is controlled per-section via composition_plan
        music_duration = total_expected_duration

        # Extract panel_local_styles from lyrics result if available
        pls = None
        if lyrics_result and hasattr(lyrics_result, 'panel_local_styles'):
            pls = lyrics_result.panel_local_styles

        # Launch both tasks in parallel
        video_task = asyncio.create_task(
            self._generate_all_clips(panels, panel_paths, clip_duration, story_id)
        )
        music_task = asyncio.create_task(
            self._generate_music_task(
                tags, lyrics, music_duration, clip_duration,
                vocal_style=vocal_style,
                negative_tags=negative_tags,
                bpm=bpm,
                panel_local_styles=pls,
            )
        )

        # Wait for both (report progress as they complete)
        clips = None
        music_result = None
        done_tasks = set()

        pending = {video_task, music_task}
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task is video_task:
                    try:
                        clips = task.result()
                        valid_clips_count = sum(1 for p, _ in clips if p is not None)
                        yield AnimationStreamEvent('video_progress', {
                            'message': f'All clips generated ({valid_clips_count}/{clip_count} successful)',
                        })
                    except Exception as e:
                        logger.error(f"[AnimatedStory] Video generation failed: {e}")
                        yield AnimationStreamEvent('error', {
                            'message': f'Video generation failed: {str(e)[:100]}'
                        })
                        # Cancel music task if video fails
                        music_task.cancel()
                        return

                elif task is music_task:
                    try:
                        music_result = task.result()
                        yield AnimationStreamEvent('music_progress', {
                            'message': f'Music ready: {music_result.duration_seconds:.1f}s',
                            'audio_path': str(music_result.audio_path),
                        })
                    except Exception as e:
                        logger.error(f"[AnimatedStory] Music generation failed: {e}")
                        yield AnimationStreamEvent('music_progress', {
                            'message': f'Music failed: {str(e)[:80]} — continuing without music',
                        })
                        music_result = None

            await asyncio.sleep(0)

        # Step 4: Concatenate clips → base video
        yield AnimationStreamEvent('compose', {
            'message': 'Concatenating video clips...'
        })
        await asyncio.sleep(0)

        valid_clip_paths = [p for p, _ in clips if p is not None]
        if not valid_clip_paths:
            yield AnimationStreamEvent('error', {'message': 'No video clips generated successfully'})
            return

        try:
            total_duration = sum(dur for _, dur in clips if dur)

            base_video_path = await self.composer.concatenate_scenes(
                scene_paths=valid_clip_paths,
                output_name=f"story_{story_id}_base",
            )

            # Step 5: Add music audio to video
            if music_result and music_result.audio_path.exists():
                yield AnimationStreamEvent('compose', {
                    'message': 'Adding music to video...'
                })
                await asyncio.sleep(0)

                video_with_music = await self.composer.add_audio_to_video(
                    video_path=base_video_path,
                    audio_path=music_result.audio_path,
                    output_name=f"story_{story_id}_with_music",
                )
            else:
                video_with_music = base_video_path

            # Step 6: Align lyrics + render captions
            final_video = video_with_music

            if enable_lyrics and music_result and music_result.audio_path.exists():
                try:
                    yield AnimationStreamEvent('caption_progress', {
                        'message': 'Preparing panel-locked lyrics captions...'
                    })
                    await asyncio.sleep(0)

                    # Panel-locked captions: lyrics lines are grouped by panel.
                    # With couplet structure (2 lines/panel), each panel's 4s window
                    # is split between its lines for sequential karaoke display.
                    lyrics_lines = self._extract_lyrics_lines(lyrics)
                    video_duration_ms = int(total_duration * 1000)
                    clip_duration_ms = clip_duration * 1000

                    if lyrics_lines:
                        yield AnimationStreamEvent('caption_progress', {
                            'message': f'Rendering rolling lyrics ({len(lyrics_lines)} lines)...'
                        })
                        await asyncio.sleep(0)

                        renderer = self._get_renderer()
                        from skills.render_captions import CaptionSegment, WordSegment as RWordSegment

                        # Group lyrics lines by panel (e.g., 8 lines → 4 groups of 2)
                        lines_per_panel = max(1, len(lyrics_lines) // max(clip_count, 1))
                        panel_lyrics = []
                        for pi in range(clip_count):
                            start_idx = pi * lines_per_panel
                            end_idx = min(start_idx + lines_per_panel, len(lyrics_lines))
                            panel_lyrics.append(lyrics_lines[start_idx:end_idx])

                        caption_segments = []
                        for pi, lines_group in enumerate(panel_lyrics):
                            panel_start_ms = pi * clip_duration_ms
                            panel_end_ms = min((pi + 1) * clip_duration_ms, video_duration_ms)

                            if panel_start_ms >= video_duration_ms:
                                break

                            margin_ms = clip_duration_ms // 10  # 400ms for 4s clips
                            caption_start = panel_start_ms + margin_ms
                            caption_end = panel_end_ms - margin_ms
                            total_caption_ms = caption_end - caption_start

                            # Split time evenly between lines in the group
                            line_duration_ms = total_caption_ms // max(len(lines_group), 1)

                            for li, line in enumerate(lines_group):
                                line_start = caption_start + li * line_duration_ms
                                line_end = min(line_start + line_duration_ms, caption_end)

                                # Spread words evenly within this line's window
                                words = line.split()
                                word_duration = (line_end - line_start) // max(len(words), 1)
                                word_segments = []
                                for wi, word in enumerate(words):
                                    ws = line_start + wi * word_duration
                                    we = min(ws + word_duration, line_end)
                                    word_segments.append(RWordSegment(
                                        text=word,
                                        startMs=ws,
                                        endMs=we,
                                    ))

                                caption_segments.append(CaptionSegment(
                                    text=line,
                                    startMs=line_start,
                                    endMs=line_end,
                                    speaker="\u266a",  # ♪ musical note
                                    words=word_segments,
                                ))

                        # Log caption-to-panel mapping
                        for ci, seg in enumerate(caption_segments):
                            panel_idx = ci // max(lines_per_panel, 1) + 1
                            logger.info(
                                f"[AnimatedStory] Caption {ci+1}: '{seg.text}' "
                                f"@ {seg.startMs}-{seg.endMs}ms (panel {panel_idx})"
                            )

                        if caption_segments:
                            final_video = await renderer.render_with_captions(
                                video_path=video_with_music,
                                captions=caption_segments,
                                output_name=f"story_{story_id}_final",
                            )

                except ImportError:
                    logger.warning("[AnimatedStory] Remotion not available, skipping lyrics")
                except Exception as e:
                    logger.warning(f"[AnimatedStory] Lyrics rendering failed: {e}")

            # Step 7: Verify output
            verification = verify_video(
                path=final_video,
                expected_duration=total_duration,
                expected_width=1080,
                expected_height=1920,
                require_audio=music_result is not None,
                duration_tolerance=2.0,
            )

            # Auto-retry with forced normalization on resolution mismatch
            if not verification.passed and any("Resolution" in f for f in verification.failures):
                logger.warning("[AnimatedStory] Verification failed (resolution), retrying with normalization")
                base_video_path = await self.composer.concatenate_scenes(
                    scene_paths=valid_clip_paths,
                    output_name=f"story_{story_id}_base_norm",
                    target_width=1080,
                    target_height=1920,
                )
                if music_result and music_result.audio_path.exists():
                    final_video = await self.composer.add_audio_to_video(
                        video_path=base_video_path,
                        audio_path=music_result.audio_path,
                        output_name=f"story_{story_id}_with_music_norm",
                    )
                else:
                    final_video = base_video_path
                verification = verify_video(
                    path=final_video,
                    expected_duration=total_duration,
                    expected_width=1080,
                    expected_height=1920,
                    require_audio=music_result is not None,
                    duration_tolerance=2.0,
                )

            # Derive browser URL from the actual file path
            # Files under assets/ are served at /assets/
            try:
                assets_root = Path(__file__).parent.parent.parent / "assets"
                rel_path = final_video.resolve().relative_to(assets_root.resolve())
                final_url = f"/assets/{rel_path}"
            except ValueError:
                final_url = f"/assets/outputs/final/{final_video.name}"

            yield AnimationStreamEvent('complete', {
                'story_id': story_id,
                'final_video_path': final_url,
                'total_duration': round(total_duration, 2),
                'clip_count': len(valid_clip_paths),
                'clips_attempted': clip_count,
                'clips_failed': clip_count - len(valid_clip_paths),
                'has_music': music_result is not None,
                'has_lyrics': enable_lyrics and music_result is not None,
                'music_tags': tags,
                'mood': mood,
                'verified': verification.passed,
                'actual_duration': round(verification.actual_duration, 2),
                'actual_resolution': f"{verification.actual_width}x{verification.actual_height}",
                'verification_failures': verification.failures if not verification.passed else [],
            })

            logger.info(f"[AnimatedStory] Music pipeline complete: {final_video} (verified={verification.passed})")

        except Exception as e:
            logger.error(f"[AnimatedStory] Music pipeline error: {e}")
            yield AnimationStreamEvent('error', {
                'message': f'Music pipeline failed: {str(e)[:100]}'
            })

    async def generate_animated_story_with_music(
        self,
        manga_result: MangaResult,
        characters: list[dict] = None,
        character_name: str = "",
        story_summary: str = "",
        clip_duration: int = 4,
        enable_lyrics: bool = True,
        custom_tags: str = None,
        custom_lyrics: str = None,
    ) -> AnimatedStoryResult:
        """
        Generate animated story with music (non-streaming).

        For progress tracking, use generate_animated_story_with_music_streaming.

        Returns:
            AnimatedStoryResult with final video path
        """
        result = AnimatedStoryResult(
            story_id="",
            final_video_path=None,
            total_duration=0.0,
            clip_count=0,
            video_paths=[],
        )

        async for event in self.generate_animated_story_with_music_streaming(
            manga_result=manga_result,
            characters=characters,
            character_name=character_name,
            story_summary=story_summary,
            clip_duration=clip_duration,
            enable_lyrics=enable_lyrics,
            custom_tags=custom_tags,
            custom_lyrics=custom_lyrics,
        ):
            if event.type == 'start':
                result.story_id = event.data['story_id']
            elif event.type == 'complete':
                result.final_video_path = Path(event.data['final_video_path'])
                result.total_duration = event.data['total_duration']
                result.clip_count = event.data['clip_count']
            elif event.type == 'error':
                raise RuntimeError(event.data['message'])

        return result
