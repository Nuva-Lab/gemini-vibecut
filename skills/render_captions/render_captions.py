"""
Caption Renderer: Burn karaoke captions into video using FFmpeg ASS subtitles.

Takes a video file and aligned captions, renders with styled subtitle overlay.
Uses FFmpeg's subtitles filter with ASS format for karaoke word-level highlighting.

Performance: ~20s for 16s 1080x1920 video (vs ~6min with Remotion headless Chrome).
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)


@dataclass
class WordSegment:
    """Word-level timing for karaoke effect."""
    text: str
    startMs: int
    endMs: int


@dataclass
class CaptionSegment:
    """Caption segment with word-level timing."""
    text: str
    startMs: int
    endMs: int
    speaker: Optional[str] = None
    words: list[WordSegment] = None

    def __post_init__(self):
        if self.words is None:
            self.words = []

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "text": self.text,
            "startMs": self.startMs,
            "endMs": self.endMs,
            "speaker": self.speaker,
            "words": [{"text": w.text, "startMs": w.startMs, "endMs": w.endMs} for w in self.words],
        }


def _ms_to_ass_time(ms: int) -> str:
    """Convert milliseconds to ASS timestamp format: H:MM:SS.cc (centiseconds)."""
    total_cs = ms // 10
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _generate_ass_content(
    captions: list[CaptionSegment],
    video_width: int = 1080,
    video_height: int = 1920,
) -> str:
    """
    Generate ASS subtitle content with karaoke word highlighting.

    ASS karaoke \\k behavior:
    - Words START as SecondaryColour (before the karaoke sweep)
    - Words FILL TO PrimaryColour (after the sweep passes)
    So: PrimaryColour = gold (sung), SecondaryColour = white (not yet sung)
    """
    # ASS colors are in &HAABBGGRR format
    white = "&H00FFFFFF"
    gold = "&H0000D7FF"  # #FFD700 → BGR 00,D7,FF
    black_outline = "&H00000000"
    bg_color = "&HC0000000"  # Black with ~75% opacity

    header = f"""[Script Info]
Title: VibeCut Captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: {video_width}
PlayResY: {video_height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,Noto Sans,56,{gold},{white},{black_outline},{bg_color},-1,0,0,0,100,100,1,0,3,4,0,2,40,40,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = []
    for seg in captions:
        start = _ms_to_ass_time(seg.startMs)
        end = _ms_to_ass_time(seg.endMs)

        if seg.words:
            # Build karaoke line with \k tags (duration in centiseconds)
            parts = []
            for word in seg.words:
                duration_cs = max(1, (word.endMs - word.startMs) // 10)
                # Escape ASS special chars in word text
                escaped = word.text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                parts.append(f"{{\\k{duration_cs}}}{escaped}")
            text = " ".join(parts)
        else:
            # No word timing — show full text
            text = seg.text

        lines.append(f"Dialogue: 0,{start},{end},Lyric,,0,0,0,,{text}")

    return header + "\n".join(lines) + "\n"


class CaptionRenderer:
    """
    Render video with karaoke captions using FFmpeg ASS subtitles.

    Usage:
        renderer = CaptionRenderer()
        output = await renderer.render_with_captions(
            video_path=Path("video.mp4"),
            captions=[CaptionSegment(...)],
        )
    """

    def __init__(self, output_dir: Path = None):
        """Initialize renderer with output directory."""
        self.output_dir = output_dir or (OUTPUT_DIR / "final")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_video_info(self, video_path: Path) -> tuple[int, int, float]:
        """Get video width, height, and duration in ms using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-show_entries", "format=duration",
            "-of", "csv=p=0:s=,",
            str(video_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            parts = result.stdout.strip().split("\n")
            # First line: width,height  Second line: duration
            wh = parts[0].split(",")
            width, height = int(wh[0]), int(wh[1])
            duration_s = float(parts[1]) if len(parts) > 1 else 16.0
            return width, height, duration_s * 1000
        except Exception as e:
            logger.warning(f"Could not probe video: {e}")
            return 1080, 1920, 16000

    async def render_with_captions(
        self,
        video_path: Path,
        captions: list[CaptionSegment],
        audio_path: Path = None,
        output_name: str = None,
        audio_volume: float = 1.0,
        composition_id: str = "MangaClip",
    ) -> Path:
        """
        Render video with karaoke captions overlay using FFmpeg.

        Args:
            video_path: Path to input video file
            captions: List of CaptionSegment with word-level timing
            audio_path: Optional separate audio track (replaces video audio)
            output_name: Output filename (without extension)
            audio_volume: Volume for audio track (0-1)
            composition_id: Ignored (kept for API compatibility)

        Returns:
            Path to rendered video with captions
        """
        video_path = Path(video_path).resolve()
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        if output_name is None:
            import uuid
            output_name = f"captioned_{uuid.uuid4().hex[:8]}"

        output_path = self.output_dir / f"{output_name}.mp4"

        # Probe video for resolution; target 1080x1920 output
        src_width, src_height, _ = self._get_video_info(video_path)
        target_width, target_height = 1080, 1920
        needs_scale = (src_width != target_width or src_height != target_height)

        # Generate ASS at target resolution (captions positioned for final output)
        ass_content = _generate_ass_content(captions, target_width, target_height)
        ass_path = self.output_dir / f"{output_name}.ass"
        ass_path.write_text(ass_content, encoding="utf-8")

        logger.info(f"Rendering captions with FFmpeg: {len(captions)} segments")

        if needs_scale:
            logger.info(f"Will scale {src_width}x{src_height} → {target_width}x{target_height}")

        # Run FFmpeg in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._run_ffmpeg(
                video_path, ass_path, output_path, audio_path, audio_volume,
                scale_to=(target_width, target_height) if needs_scale else None,
            )
        )

        # Clean up ASS file
        ass_path.unlink(missing_ok=True)

        return result

    def _run_ffmpeg(
        self,
        video_path: Path,
        ass_path: Path,
        output_path: Path,
        audio_path: Optional[Path],
        audio_volume: float,
        scale_to: tuple[int, int] = None,
    ) -> Path:
        """Run FFmpeg subtitle burn-in synchronously."""
        # Escape the ASS path for FFmpeg filter (colons and backslashes need escaping)
        escaped_ass = str(ass_path).replace("\\", "\\\\").replace(":", "\\:")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
        ]

        # If separate audio track, add it
        if audio_path and Path(audio_path).exists():
            cmd.extend(["-i", str(audio_path)])

        # Video filter chain: optional scale + subtitle burn-in
        vf_parts = []
        if scale_to:
            w, h = scale_to
            vf_parts.append(f"scale={w}:{h}")
        vf_parts.append(f"subtitles={escaped_ass}")
        vf_chain = ",".join(vf_parts)

        cmd.extend([
            "-vf", vf_chain,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-color_range", "tv",
            "-colorspace", "bt709",
            "-color_trc", "bt709",
            "-color_primaries", "bt709",
        ])

        # Audio handling
        if audio_path and Path(audio_path).exists():
            cmd.extend([
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:a", "aac", "-b:a", "128k",
            ])
            if audio_volume != 1.0:
                cmd.extend(["-af", f"volume={audio_volume}"])
        else:
            cmd.extend(["-c:a", "copy"])

        cmd.append(str(output_path))

        logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,  # 2 min timeout (plenty for FFmpeg)
            )
            logger.info(f"Caption render complete: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg caption render failed: {e.stderr[-500:]}")
            raise RuntimeError(f"FFmpeg caption render failed: {e.stderr[-500:]}")
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg caption render timed out after 2 minutes")
            raise RuntimeError("FFmpeg caption render timed out")

    async def render_concatenated_video(
        self,
        clip_paths: list[Path],
        clip_captions: list[list[CaptionSegment]],
        audio_paths: list[Path] = None,
        output_name: str = None,
    ) -> Path:
        """
        Render multiple clips with captions, then concatenate.

        Args:
            clip_paths: List of video clip paths
            clip_captions: List of caption lists, one per clip
            audio_paths: Optional list of audio paths, one per clip
            output_name: Output filename

        Returns:
            Path to final concatenated video
        """
        if len(clip_paths) != len(clip_captions):
            raise ValueError("Number of clips must match number of caption lists")

        audio_paths = audio_paths or [None] * len(clip_paths)
        rendered_clips = []

        for i, (video_path, captions, audio_path) in enumerate(
            zip(clip_paths, clip_captions, audio_paths)
        ):
            clip_output = await self.render_with_captions(
                video_path=video_path,
                captions=captions,
                audio_path=audio_path,
                output_name=f"clip_{i:02d}_captioned",
            )
            rendered_clips.append(clip_output)

        if output_name is None:
            import uuid
            output_name = f"final_{uuid.uuid4().hex[:8]}"

        final_output = self.output_dir / f"{output_name}.mp4"

        # Create concat file
        concat_file = self.output_dir / f"{output_name}_concat.txt"
        with open(concat_file, "w") as f:
            for clip in rendered_clips:
                f.write(f"file '{clip}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(final_output),
        ]

        logger.info(f"Concatenating {len(rendered_clips)} captioned clips")

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            concat_file.unlink()
            logger.info(f"Final video: {final_output}")
            return final_output
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg concat error: {e.stderr.decode()}")
            raise
