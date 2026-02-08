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
        panel_local_styles: list[list[str]] = None,
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
        - respect_sections_durations=True for exact timing per section
        - Multi-line sections (2 lyric lines per panel for richer vocals)

        Args:
            prompt: Style/genre description (used for positive_global_styles)
            lyrics: Song lyrics with [Verse 1]/[Chorus] structure tags (8 lines for 4 panels)
            duration: Total duration in seconds (ignored, derived from sections)
            clip_duration: Duration per panel/section in seconds (default 4)
            panel_styles: Optional per-panel local style overrides (legacy, single string each)
            panel_local_styles: Gemini-generated per-section local styles (list of lists)
            vocal_style: Vocal delivery descriptor (e.g. "breathy", "energetic")
            negative_tags: Comma-separated styles to avoid
            bpm: Suggested BPM (0 = let model decide)

        Returns:
            MusicResult with audio path and metadata
        """
        import re

        # Parse lyrics into section groups by structure tags
        # Input: "[Verse 1]\nLine1\nLine2\n[Verse 2]\nLine3\nLine4\n..."
        # Output: [["Line1", "Line2"], ["Line3", "Line4"], ...]
        num_sections = max(1, duration // clip_duration) if clip_duration > 0 else 4
        sections_lines = []
        current_section = []
        for line in lyrics.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r'^\[.*\]$', stripped):
                if current_section:
                    sections_lines.append(current_section)
                    current_section = []
            else:
                current_section.append(stripped)
        if current_section:
            sections_lines.append(current_section)

        # If structure-tag parsing didn't produce the right number, fall back to even grouping
        if len(sections_lines) != num_sections:
            all_lines = []
            for line in lyrics.splitlines():
                stripped = line.strip()
                if stripped and not re.match(r'^\[.*\]$', stripped):
                    all_lines.append(stripped)
            if not all_lines:
                all_lines = ["la la la", "la la la", "la la la", "la la la",
                             "la la la", "la la la", "la la la", "la la la"]
            lines_per = max(1, len(all_lines) // num_sections)
            sections_lines = []
            for i in range(0, len(all_lines), lines_per):
                sections_lines.append(all_lines[i:i + lines_per])
            while len(sections_lines) < num_sections:
                sections_lines.append(["la la la"])
            sections_lines = sections_lines[:num_sections]

        # Parse global styles from prompt (comma-separated tags)
        global_styles = [s.strip() for s in prompt.split(",") if s.strip()]

        # Ensure full instrumentation from first beat
        if not any("full instrumentation" in s.lower() for s in global_styles):
            global_styles.append("full instrumentation from first beat")
        if not any("continuous" in s.lower() for s in global_styles):
            global_styles.append("continuous backing track")

        # Enrich global styles with vocal delivery and BPM
        if vocal_style and vocal_style not in " ".join(global_styles).lower():
            global_styles.append(f"{vocal_style} vocals")
        if bpm > 0 and not any("bpm" in s.lower() for s in global_styles):
            global_styles.append(f"{bpm} BPM")

        # Parse negative styles — always avoid sparse/dry output
        must_avoid = ["spoken word", "silence", "slow intro", "fade in", "sparse", "thin"]
        if negative_tags:
            neg_styles = [s.strip() for s in negative_tags.split(",") if s.strip()]
            # Ensure essentials are present
            existing_lower = {s.lower() for s in neg_styles}
            for ma in must_avoid:
                if ma.lower() not in existing_lower:
                    neg_styles.append(ma)
        else:
            neg_styles = must_avoid[:]

        # Build sections — one per panel, multi-line
        section_names = ["Verse 1", "Verse 2", "Chorus", "Outro"]
        default_local_pos = [
            ["gentle", "soft piano", "building", "warm opening"],
            ["rising energy", "melodic", "driving rhythm", "building momentum"],
            ["energetic", "powerful", "catchy hook", "anthemic", "full energy"],
            ["triumphant", "warm resolution", "uplifting", "emotional peak"],
        ]
        default_local_neg = [
            ["loud", "heavy drums", "aggressive"],
            ["slow", "quiet", "subdued"],
            ["subdued", "quiet", "restrained"],
            ["abrupt", "dark", "harsh"],
        ]

        from elevenlabs.types.song_section import SongSection

        sections = []
        for i, sec_lines in enumerate(sections_lines):
            name = section_names[i] if i < len(section_names) else f"Section {i+1}"

            # Local styles priority: Gemini-provided > panel_styles override > default
            if panel_local_styles and i < len(panel_local_styles) and panel_local_styles[i]:
                local_pos = list(panel_local_styles[i])
            elif panel_styles and i < len(panel_styles):
                local_pos = [panel_styles[i]]
            else:
                local_pos = list(default_local_pos[i]) if i < len(default_local_pos) else ["melodic"]

            local_neg = list(default_local_neg[i]) if i < len(default_local_neg) else []

            # Add vocal delivery to local styles
            if vocal_style:
                local_pos = local_pos + [f"{vocal_style} delivery"]

            sections.append(SongSection(
                section_name=name,
                positive_local_styles=local_pos,
                negative_local_styles=local_neg,
                duration_ms=clip_duration * 1000,
                lines=sec_lines,
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
            f"{len(sections)} sections, {sum(len(s.lines) for s in sections)} lyric lines, "
            f"styles={global_styles[:3]}, vocal={vocal_style or 'default'}, "
            f"neg_global={neg_styles[:3]}"
        )
        for i, s in enumerate(sections):
            logger.info(
                f"[ElevenLabs]   Section {i+1} '{s.section_name}': "
                f"lines={s.lines}, pos={s.positive_local_styles[:3]}, "
                f"neg={s.negative_local_styles[:2]}"
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
