"""
Video Output Verification — ffprobe-based checks for pipeline output.

Catches corrupt concats, resolution mismatches, missing audio, and
duration drift before reporting success to the user.
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of video verification checks."""
    passed: bool
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    actual_duration: float = 0.0
    actual_width: int = 0
    actual_height: int = 0
    has_video: bool = False
    has_audio: bool = False
    file_size_bytes: int = 0


def verify_video(
    path: Path,
    expected_duration: Optional[float] = None,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
    require_audio: bool = False,
    min_file_size: int = 10_000,
    duration_tolerance: float = 2.0,
) -> VerificationResult:
    """
    Verify a video file meets expected specs via ffprobe.

    Args:
        path: Path to video file
        expected_duration: Expected duration in seconds (checked with tolerance)
        expected_width: Expected pixel width
        expected_height: Expected pixel height
        require_audio: Whether audio stream is required
        min_file_size: Minimum file size in bytes (default 10KB)
        duration_tolerance: Allowed deviation in seconds (default 2.0)

    Returns:
        VerificationResult with pass/fail and details
    """
    result = VerificationResult(passed=True)
    path = Path(path)

    # Check 1: File exists
    if not path.exists():
        result.passed = False
        result.failures.append(f"File not found: {path}")
        return result
    result.checks.append("file_exists")

    # Check 2: File size
    result.file_size_bytes = path.stat().st_size
    if result.file_size_bytes < min_file_size:
        result.passed = False
        result.failures.append(
            f"File too small: {result.file_size_bytes} bytes (min {min_file_size})"
        )
    else:
        result.checks.append(f"file_size={result.file_size_bytes}")

    # Check 3: Probe with ffprobe
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,codec_type,codec_name,duration",
        "-show_entries", "format=duration,nb_streams",
        "-of", "json",
        str(path),
    ]

    try:
        probe = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(probe.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        result.passed = False
        result.failures.append(f"ffprobe failed: {e}")
        return result

    streams = data.get("streams", [])
    fmt = data.get("format", {})

    # Parse streams
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    result.has_video = len(video_streams) > 0
    result.has_audio = len(audio_streams) > 0

    # Check 4: Video stream exists
    if not result.has_video:
        result.passed = False
        result.failures.append("No video stream found")
        return result
    result.checks.append("has_video_stream")

    # Check 5: Audio stream (if required)
    if require_audio and not result.has_audio:
        result.passed = False
        result.failures.append("No audio stream found (required)")
    elif result.has_audio:
        result.checks.append("has_audio_stream")

    # Parse video properties
    vs = video_streams[0]
    result.actual_width = int(vs.get("width", 0))
    result.actual_height = int(vs.get("height", 0))

    # Duration: prefer format duration (more reliable for concatenated files)
    result.actual_duration = float(fmt.get("duration", 0) or vs.get("duration", 0))

    # Check 6: Duration within tolerance
    if expected_duration is not None:
        diff = abs(result.actual_duration - expected_duration)
        if diff > duration_tolerance:
            result.passed = False
            result.failures.append(
                f"Duration mismatch: expected {expected_duration:.1f}s, "
                f"got {result.actual_duration:.1f}s (tolerance {duration_tolerance}s)"
            )
        else:
            result.checks.append(f"duration={result.actual_duration:.1f}s")

    # Check 7: Resolution match
    if expected_width is not None and expected_height is not None:
        if result.actual_width != expected_width or result.actual_height != expected_height:
            result.passed = False
            result.failures.append(
                f"Resolution mismatch: expected {expected_width}x{expected_height}, "
                f"got {result.actual_width}x{result.actual_height}"
            )
        else:
            result.checks.append(f"resolution={result.actual_width}x{result.actual_height}")

    if result.passed:
        logger.info(f"Verification PASSED: {path.name} ({', '.join(result.checks)})")
    else:
        logger.warning(f"Verification FAILED: {path.name} — {result.failures}")

    return result
