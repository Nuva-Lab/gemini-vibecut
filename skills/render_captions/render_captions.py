"""
Caption Renderer: Render video with rolling karaoke captions using Remotion.

Takes a video file and aligned captions, renders with motion graphics overlay.
"""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# Remotion project directory
REMOTION_DIR = Path(__file__).parent.parent.parent / "remotion"


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


class CaptionRenderer:
    """
    Render video with rolling karaoke captions using Remotion.

    Usage:
        renderer = CaptionRenderer()
        output = await renderer.render_with_captions(
            video_path=Path("video.mp4"),
            captions=[CaptionSegment(...)],
            audio_path=Path("audio.wav"),  # optional
        )
    """

    def __init__(self, output_dir: Path = None):
        """Initialize renderer with output directory."""
        self.output_dir = output_dir or (OUTPUT_DIR / "final")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.remotion_dir = REMOTION_DIR
        self._check_remotion()

    def _check_remotion(self):
        """Check if Remotion is available."""
        node_modules = self.remotion_dir / "node_modules"
        if not node_modules.exists():
            logger.warning(
                f"Remotion node_modules not found at {self.remotion_dir}. "
                "Run 'npm install' in the remotion directory."
            )

    def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration in milliseconds using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip()) * 1000  # Convert to ms
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.warning(f"Could not get video duration: {e}")
            return 16000  # Default 16s

    def _stage_file_for_remotion(self, file_path: Path) -> str:
        """
        Copy a file into Remotion's public/ dir so it's accessible during render.
        Returns the staticFile()-compatible path (just the filename).
        """
        import shutil
        public_dir = self.remotion_dir / "public"
        public_dir.mkdir(parents=True, exist_ok=True)
        dest = public_dir / file_path.name
        if not dest.exists() or dest.stat().st_mtime < file_path.stat().st_mtime:
            shutil.copy2(file_path, dest)
        # Remotion serves public/ files at root, so just use the filename
        return file_path.name

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
        Render video with karaoke captions overlay.

        Args:
            video_path: Path to input video file
            captions: List of CaptionSegment with word-level timing
            audio_path: Optional separate audio track (TTS dialogue)
            output_name: Output filename (without extension)
            audio_volume: Volume for audio track (0-1)
            composition_id: Remotion composition ID (MangaClip or MangaClipHorizontal)

        Returns:
            Path to rendered video with captions
        """
        video_path = Path(video_path).resolve()
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        # Generate output name if not provided
        if output_name is None:
            import uuid
            output_name = f"captioned_{uuid.uuid4().hex[:8]}"

        output_path = self.output_dir / f"{output_name}.mp4"

        # Get video duration
        duration_ms = self._get_video_duration(video_path)
        duration_frames = int((duration_ms / 1000) * 30) - 1  # 30fps, 0-indexed

        # Stage video into Remotion's public/ so it's accessible during render
        video_filename = self._stage_file_for_remotion(video_path)

        # Prepare props for Remotion (use staticFile-compatible relative path)
        props = {
            "videoSrc": video_filename,
            "captions": [c.to_dict() for c in captions],
            "audioVolume": audio_volume,
        }
        if audio_path:
            audio_filename = self._stage_file_for_remotion(Path(audio_path).resolve())
            props["audioSrc"] = audio_filename

        # Write props to temp file
        props_file = self.output_dir / f"{output_name}_props.json"
        with open(props_file, "w") as f:
            json.dump(props, f, ensure_ascii=False, indent=2)

        logger.info(f"Rendering captions with Remotion: {len(captions)} segments")

        # Run Remotion render in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._run_remotion(
                props_file, output_path, duration_frames, composition_id
            )
        )

        # Clean up props file
        props_file.unlink(missing_ok=True)

        return result

    def _run_remotion(
        self,
        props_file: Path,
        output_path: Path,
        duration_frames: int,
        composition_id: str,
    ) -> Path:
        """Run Remotion render command synchronously."""
        cmd = [
            "npx", "remotion", "render",
            composition_id,
            str(output_path),
            "--props", str(props_file),
            "--frames", f"0-{duration_frames}",
        ]

        logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.remotion_dir),
                capture_output=True,
                text=True,
                check=True,
                timeout=300,  # 5 min timeout
            )
            logger.info(f"Remotion render complete: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Remotion render failed: {e.stderr}")
            raise RuntimeError(f"Remotion render failed: {e.stderr[:500]}")
        except subprocess.TimeoutExpired:
            logger.error("Remotion render timed out after 5 minutes")
            raise RuntimeError("Remotion render timed out")

    async def render_concatenated_video(
        self,
        clip_paths: list[Path],
        clip_captions: list[list[CaptionSegment]],
        audio_paths: list[Path] = None,
        output_name: str = None,
    ) -> Path:
        """
        Render multiple clips with captions, then concatenate.

        For each clip:
        1. Add captions overlay
        2. Merge with corresponding audio
        Then concatenate all clips.

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

        # Concatenate using FFmpeg
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
