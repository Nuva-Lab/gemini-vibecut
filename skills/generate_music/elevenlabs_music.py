"""
ElevenLabs Music Generation — Cloud API client.

Generates background songs with vocals and lyrics using ElevenLabs Music API.
Per-section duration and lyrics control via composition_plan.

API docs: https://elevenlabs.io/docs/overview/capabilities/music
"""

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)


@dataclass
class MusicResult:
    """Result from ElevenLabs music generation."""
    audio_path: Path
    duration_seconds: float
    tags: str
    lyrics: str
    seed: int  # Not used by ElevenLabs, kept for interface compat


class ElevenLabsMusicGenerator:
    """
    Client for ElevenLabs Music API.

    Uses composition_plan with per-section duration and lyrics for
    precise control over where vocals appear in the song.

    Usage:
        gen = ElevenLabsMusicGenerator()
        result = await gen.generate_music(
            prompt="upbeat anime pop, female vocals",
            lyrics="[Verse 1]\\nLook what I found\\n[Verse 2]\\nA treasure map",
            duration=16,
            clip_duration=4,
        )
    """

    def __init__(
        self,
        api_key: str = None,
        output_dir: Path = None,
    ):
        import os
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY not set")
        self.output_dir = output_dir or (OUTPUT_DIR / "music")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_music(
        self,
        prompt: str,
        lyrics: str,
        duration: int = 16,
        clip_duration: int = 4,
        panel_styles: list[str] = None,
        vocal_style: str = "",
        negative_tags: str = "",
        bpm: int = 0,
    ) -> MusicResult:
        """
        Generate music with per-panel lyrics via ElevenLabs composition_plan.

        Uses ElevenLabs best practices:
        - Intent-based global styles (genre + instruments + vocal delivery + BPM)
        - Per-section local styles matching story arc progression
        - Negative styles to avoid unwanted musical directions
        - respect_sections_durations=True for exact 4s per section

        Args:
            prompt: Style/genre description (used for positive_global_styles)
            lyrics: Song lyrics with [Verse 1]/[Chorus] structure tags
            duration: Total duration in seconds (ignored, derived from sections)
            clip_duration: Duration per panel/section in seconds (default 4)
            panel_styles: Optional per-panel local style overrides
            vocal_style: Vocal delivery descriptor (e.g. "breathy", "energetic")
            negative_tags: Comma-separated styles to avoid
            bpm: Suggested BPM (0 = let model decide)

        Returns:
            MusicResult with audio path and metadata
        """
        import re

        # Parse lyrics into lines (strip structure tags)
        lines = []
        for line in lyrics.splitlines():
            stripped = line.strip()
            if stripped and not re.match(r'^\[.*\]$', stripped):
                lines.append(stripped)

        if not lines:
            lines = ["la la la", "la la la", "la la la", "la la la"]

        # Parse global styles from prompt (comma-separated tags)
        global_styles = [s.strip() for s in prompt.split(",") if s.strip()]

        # Enrich global styles with vocal delivery and BPM if provided
        if vocal_style and vocal_style not in " ".join(global_styles).lower():
            global_styles.append(f"{vocal_style} vocals")
        if bpm > 0 and not any("bpm" in s.lower() for s in global_styles):
            global_styles.append(f"{bpm} BPM")

        # Parse negative styles
        neg_styles = ["spoken word"]  # Always avoid spoken word for music
        if negative_tags:
            neg_styles = [s.strip() for s in negative_tags.split(",") if s.strip()]

        # Build sections — one per lyrics line
        # Story arc: setup → action → twist → payoff
        section_names = ["Verse 1", "Verse 2", "Chorus", "Outro"]
        default_local = [
            ["gentle", "building", "soft opening"],
            ["rising energy", "melodic", "building momentum"],
            ["energetic", "powerful", "catchy hook"],
            ["triumphant", "uplifting", "resolving", "emotional peak"],
        ]

        from elevenlabs.types.song_section import SongSection

        sections = []
        for i, line in enumerate(lines):
            name = section_names[i] if i < len(section_names) else f"Section {i+1}"

            # Local styles: use panel_styles override, or default arc progression
            if panel_styles and i < len(panel_styles):
                local_pos = [panel_styles[i]]
            else:
                local_pos = default_local[i] if i < len(default_local) else ["melodic"]

            # Add vocal delivery to local styles for consistency
            if vocal_style:
                local_pos = local_pos + [f"{vocal_style} delivery"]

            sections.append(SongSection(
                section_name=name,
                positive_local_styles=local_pos,
                negative_local_styles=[],
                duration_ms=clip_duration * 1000,
                lines=[line],
            ))

        from elevenlabs.types.music_prompt import MusicPrompt
        plan = MusicPrompt(
            positive_global_styles=global_styles[:10],
            negative_global_styles=neg_styles[:8],
            sections=sections,
        )

        total_ms = sum(s.duration_ms for s in sections)
        logger.info(
            f"[ElevenLabs] Generating {total_ms/1000:.0f}s music: "
            f"{len(sections)} sections, styles={global_styles[:3]}, "
            f"vocal={vocal_style or 'default'}, neg={neg_styles[:3]}"
        )

        # Run blocking API call in executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._call_api(plan, prompt, lyrics),
        )
        return result

    def _call_api(self, plan, prompt: str, lyrics: str) -> MusicResult:
        """Synchronous API call (runs in executor)."""
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=self.api_key)

        t0 = time.time()
        result = client.music.compose(
            composition_plan=plan,
            respect_sections_durations=True,
            output_format="mp3_44100_128",
        )

        # Stream response to file
        import uuid
        file_id = str(uuid.uuid4())[:8]
        mp3_path = self.output_dir / f"elevenlabs_{file_id}.mp3"

        with open(mp3_path, "wb") as f:
            for chunk in result:
                f.write(chunk)

        elapsed = time.time() - t0
        logger.info(f"[ElevenLabs] Audio saved: {mp3_path} ({mp3_path.stat().st_size} bytes, {elapsed:.1f}s)")

        # Get actual duration
        actual_duration = self._get_duration(mp3_path)

        return MusicResult(
            audio_path=mp3_path,
            duration_seconds=actual_duration,
            tags=prompt,
            lyrics=lyrics,
            seed=0,
        )

    def _get_duration(self, audio_path: Path) -> float:
        """Get audio duration via ffprobe."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
                capture_output=True, text=True, check=True,
            )
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.warning(f"Could not get audio duration: {e}")
            return 0.0
