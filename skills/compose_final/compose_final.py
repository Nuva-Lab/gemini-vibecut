"""
Video Composition Skill - FFmpeg video/audio assembly.

This skill composes the final output by combining:
- Generated video scenes
- Generated background music
- Transitions and effects
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR, VIDEO_FPS

logger = logging.getLogger(__name__)


class VideoComposer:
    """
    Compose final videos using FFmpeg.

    This is the "reliable, not AI" part of the stack.
    FFmpeg handles the deterministic assembly work.
    """

    def __init__(self):
        """Initialize composer."""
        self.output_dir = OUTPUT_DIR / "final"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Verify FFmpeg is available."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
            )
            logger.info("FFmpeg is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("FFmpeg not found - composition will be limited")

    @dataclass
    class VideoProbe:
        """Result of ffprobe on a video file."""
        width: int
        height: int
        duration: float
        codec: str

    def _probe_video(self, path: Path) -> Optional["VideoComposer.VideoProbe"]:
        """
        Probe video file for resolution, duration, and codec via ffprobe.

        Returns None if probing fails.
        """
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,codec_name,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            stream = data.get("streams", [{}])[0]
            fmt = data.get("format", {})

            width = int(stream.get("width", 0))
            height = int(stream.get("height", 0))
            codec = stream.get("codec_name", "unknown")

            # Duration from stream first, fall back to format
            duration = float(stream.get("duration", 0) or fmt.get("duration", 0))

            return self.VideoProbe(width=width, height=height, duration=duration, codec=codec)
        except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError, IndexError) as e:
            logger.warning(f"Could not probe video {path}: {e}")
            return None

    def _normalize_clip(
        self,
        clip_path: Path,
        target_width: int,
        target_height: int,
        output_path: Path,
    ) -> Path:
        """
        Re-encode a clip to target resolution, preserving aspect ratio with padding.

        Uses scale+pad filter to handle aspect ratio differences cleanly.
        """
        # scale to fit within target, then pad to exact target size
        vf = (
            f"scale={target_width}:{target_height}"
            f":force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_path),
        ]

        logger.info(f"Normalizing {clip_path.name} to {target_width}x{target_height}")

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Normalize error: {e.stderr.decode()}")
            raise

    async def compose_video_with_music(
        self,
        video_path: Path,
        music_path: Path,
        output_name: str,
        music_volume: float = 0.3,
    ) -> Path:
        """
        Combine video with background music.

        Args:
            video_path: Path to video file
            music_path: Path to music file
            output_name: Name for output file
            music_volume: Volume level for music (0.0 - 1.0)

        Returns:
            Path to composed video
        """
        output_path = self.output_dir / f"{output_name}.mp4"

        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", str(video_path),
            "-i", str(music_path),
            "-filter_complex",
            f"[1:a]volume={music_volume}[music];[0:a][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ]

        logger.info(f"Composing video with music: {output_name}")

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Composed video saved to: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise

    async def concatenate_scenes(
        self,
        scene_paths: list[Path],
        output_name: str,
        transition: str = "fade",
        transition_duration: float = 0.5,
        target_width: int = 1080,
        target_height: int = 1920,
    ) -> Path:
        """
        Concatenate multiple video scenes with transitions.

        Probes all clips first — if resolutions differ (e.g. Veo 720x1280
        vs Remotion 1080x1920), normalizes all to target before concat.
        When all resolutions match, uses fast stream copy.

        Args:
            scene_paths: List of video file paths in order
            output_name: Name for output file
            transition: Transition type (fade, dissolve, etc.)
            transition_duration: Duration of transition in seconds
            target_width: Target width for normalization (default 1080)
            target_height: Target height for normalization (default 1920)

        Returns:
            Path to concatenated video
        """
        output_path = self.output_dir / f"{output_name}.mp4"

        # Probe all clips to check resolution consistency
        probes = []
        for path in scene_paths:
            probe = self._probe_video(path)
            probes.append(probe)
            if probe:
                logger.debug(f"  {path.name}: {probe.width}x{probe.height} {probe.codec} {probe.duration:.1f}s")

        # Check if all resolutions match
        resolutions = set()
        for probe in probes:
            if probe and probe.width > 0 and probe.height > 0:
                resolutions.add((probe.width, probe.height))

        needs_normalize = len(resolutions) > 1
        if needs_normalize:
            logger.warning(
                f"Resolution mismatch detected: {resolutions}. "
                f"Normalizing all clips to {target_width}x{target_height}."
            )

        # Normalize clips if needed
        clips_to_concat = []
        if needs_normalize:
            norm_dir = self.output_dir / f"{output_name}_norm"
            norm_dir.mkdir(parents=True, exist_ok=True)

            for i, path in enumerate(scene_paths):
                norm_path = norm_dir / f"clip_{i:03d}.mp4"
                try:
                    self._normalize_clip(path, target_width, target_height, norm_path)
                    clips_to_concat.append(norm_path)
                except Exception as e:
                    logger.error(f"Failed to normalize clip {i}: {e}")
                    clips_to_concat.append(path)  # fall back to original
        else:
            clips_to_concat = list(scene_paths)

        # Create concat file
        concat_file = self.output_dir / f"{output_name}_concat.txt"
        with open(concat_file, "w") as f:
            for path in clips_to_concat:
                f.write(f"file '{path}'\n")

        # Use stream copy only when all clips have matching resolution
        if needs_normalize:
            # Already re-encoded to uniform resolution, safe to stream copy
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path),
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path),
            ]

        logger.info(f"Concatenating {len(clips_to_concat)} scenes" + (" (normalized)" if needs_normalize else ""))

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            concat_file.unlink()  # Clean up temp file

            # Clean up normalized clips
            if needs_normalize:
                import shutil
                norm_dir = self.output_dir / f"{output_name}_norm"
                if norm_dir.exists():
                    shutil.rmtree(norm_dir)

            logger.info(f"Concatenated video saved to: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise

    async def concatenate_audio(
        self,
        audio_paths: list[Path],
        output_name: str,
    ) -> Path:
        """
        Concatenate multiple audio files.

        Args:
            audio_paths: List of audio file paths in order
            output_name: Name for output file

        Returns:
            Path to concatenated audio file
        """
        output_path = self.output_dir / f"{output_name}.wav"

        # Create concat file
        concat_file = self.output_dir / f"{output_name}_audio_concat.txt"
        with open(concat_file, "w") as f:
            for path in audio_paths:
                f.write(f"file '{path}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path),
        ]

        logger.info(f"Concatenating {len(audio_paths)} audio clips")

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            concat_file.unlink()  # Clean up temp file
            logger.info(f"Concatenated audio saved to: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise

    async def add_audio_to_video(
        self,
        video_path: Path,
        audio_path: Path,
        output_name: str,
    ) -> Path:
        """
        Add audio track to a silent video.

        Veo generates videos without audio tracks, so we can't use amix.
        This method adds an audio track to a silent video.

        Args:
            video_path: Path to silent video file
            audio_path: Path to audio file to add
            output_name: Name for output file

        Returns:
            Path to video with audio
        """
        output_path = self.output_dir / f"{output_name}.mp4"

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),   # Silent video
            "-i", str(audio_path),   # Audio to add
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",         # Video from first input
            "-map", "1:a:0",         # Audio from second input
            "-shortest",
            str(output_path),
        ]

        logger.info(f"Adding audio to video: {output_name}")

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Video with audio saved to: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise

    def _get_audio_duration(self, audio_path: Path) -> float:
        """
        Get duration of audio file using ffprobe.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds
        """
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.warning(f"Could not get audio duration: {e}")
            return 0.0

    async def pad_audio_to_duration(
        self,
        audio_path: Path,
        target_duration: float,
        output_name: str,
    ) -> Path:
        """
        Pad audio with silence to match target duration.

        Args:
            audio_path: Path to audio file
            target_duration: Target duration in seconds
            output_name: Name for output file

        Returns:
            Path to padded audio file
        """
        output_path = self.output_dir / f"{output_name}.wav"

        # Use FFmpeg's apad filter to extend audio with silence
        cmd = [
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-af", f"apad=whole_dur={target_duration}",
            "-c:a", "pcm_s16le",
            str(output_path),
        ]

        logger.info(f"Padding audio to {target_duration:.2f}s: {output_name}")

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg pad error: {e.stderr.decode()}")
            raise

    async def add_audio_to_clip(
        self,
        video_path: Path,
        audio_path: Path,
        video_duration: float,
        output_name: str,
    ) -> Path:
        """
        Add audio to a single video clip with proper sync.

        Pads audio if shorter than video to ensure perfect alignment.

        Args:
            video_path: Path to silent video clip
            audio_path: Path to audio file
            video_duration: Duration of video in seconds
            output_name: Name for output file

        Returns:
            Path to video clip with synced audio
        """
        output_path = self.output_dir / f"{output_name}.mp4"

        # Get audio duration
        audio_duration = self._get_audio_duration(audio_path)

        # Pad audio if shorter than video (with 0.1s tolerance)
        if audio_duration < video_duration - 0.1:
            logger.info(f"Padding audio {audio_duration:.2f}s -> {video_duration:.2f}s")
            padded_audio = await self.pad_audio_to_duration(
                audio_path, video_duration, f"{output_name}_padded"
            )
            audio_to_use = padded_audio
        else:
            audio_to_use = audio_path

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_to_use),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-t", str(video_duration),  # Force exact duration
            str(output_path),
        ]

        logger.info(f"Adding synced audio to clip: {output_name}")

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Synced clip saved to: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise

    async def add_text_overlay(
        self,
        video_path: Path,
        text: str,
        position: str = "bottom",
        output_name: str = None,
    ) -> Path:
        """
        Add text overlay to video.

        Args:
            video_path: Path to video file
            text: Text to overlay
            position: Position (top, bottom, center)
            output_name: Name for output file

        Returns:
            Path to video with overlay
        """
        output_name = output_name or f"{video_path.stem}_text"
        output_path = self.output_dir / f"{output_name}.mp4"

        # Position mapping
        positions = {
            "top": "x=(w-text_w)/2:y=50",
            "center": "x=(w-text_w)/2:y=(h-text_h)/2",
            "bottom": "x=(w-text_w)/2:y=h-text_h-50",
        }
        pos = positions.get(position, positions["bottom"])

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vf", f"drawtext=text='{text}':fontsize=48:fontcolor=white:{pos}",
            "-c:a", "copy",
            str(output_path),
        ]

        logger.info(f"Adding text overlay: '{text}'")

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Video with text saved to: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise
