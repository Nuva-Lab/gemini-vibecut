#!/usr/bin/env python3
"""
Download demo video clips WITH AUDIO for Gemini VibeCut gallery.

Uses yt-dlp + Node.js runtime to download from YouTube.
Each clip: 480p, 30fps, ≤20s, with verified audible audio.

Usage:
    python download_demo_videos.py          # download all
    python download_demo_videos.py --check  # just check existing clips
"""

import subprocess
import json
import sys
import glob
from pathlib import Path

VIDEOS_DIR = Path(__file__).parent / "videos"
VIDEOS_DIR.mkdir(exist_ok=True)

# ── Curated clips with AUDIO ─────────────────────────────────────────
# (name, youtube_url, start_sec, end_sec, description)
# These are hand-picked for diverse content with clear, audible audio.
CLIPS = [
    # --- People / Vlog ---
    (
        "vlog_clip",
        "https://www.youtube.com/watch?v=oHg5SJYRHA0",  # Rick Astley (clear vocals)
        10, 30,
        "Music video with clear vocals"
    ),
    (
        "street_walk",
        "https://www.youtube.com/watch?v=hdOkJfsMsdA",  # Tokyo night walk
        30, 50,
        "Tokyo street walk with ambient sounds"
    ),
    # --- Cooking ---
    (
        "cooking_clip",
        "https://www.youtube.com/watch?v=PUP7U5vTMM0",  # Cooking sounds
        10, 30,
        "Cooking with sizzling/kitchen sounds"
    ),
    # --- Nature ---
    (
        "nature_clip",
        "https://www.youtube.com/watch?v=eKFTSSKCzWA",  # Forest sounds
        10, 30,
        "Forest with bird/nature sounds"
    ),
    # --- Cafe / Ambient ---
    (
        "cafe_clip",
        "https://www.youtube.com/watch?v=BOdLmxy06H0",  # Cafe ambience
        30, 50,
        "Coffee shop ambience"
    ),
    # --- Music ---
    (
        "music_clip",
        "https://www.youtube.com/watch?v=kTJczUoc26U",  # Street musician
        15, 35,
        "Street music performance"
    ),
]


def run_cmd(cmd, timeout=120):
    """Run command, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"


def check_audio(path):
    """Check if video has audible audio. Returns (has_audio, mean_volume_db)."""
    rc, _, stderr = run_cmd([
        "ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "/dev/null"
    ])
    mean_vol = None
    for line in stderr.split("\n"):
        if "mean_volume" in line:
            try:
                mean_vol = float(line.split("mean_volume:")[1].strip().split(" ")[0])
            except (ValueError, IndexError):
                pass
    if mean_vol is None:
        return False, None
    return mean_vol > -70, mean_vol  # -91dB is silence, -70dB is threshold


def get_duration(path):
    """Get video duration in seconds."""
    rc, stdout, _ = run_cmd([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ])
    try:
        return float(stdout.strip())
    except ValueError:
        return 0


def download_clip(name, url, start, end, description):
    """Download a YouTube clip segment with audio."""
    output = VIDEOS_DIR / f"{name}.mp4"
    tmp_raw = VIDEOS_DIR / f".{name}_raw.mp4"
    duration = end - start

    print(f"\n[{name}] {description}")

    # Skip if already good
    if output.exists():
        has_audio, vol = check_audio(output)
        if has_audio:
            dur = get_duration(output)
            size = output.stat().st_size / 1024 / 1024
            print(f"  Already OK: {size:.1f}MB, {dur:.0f}s, {vol:.1f}dB")
            return True
        else:
            print(f"  Exists but no audio — re-downloading")
            output.unlink()

    # Step 1: Download with yt-dlp (--js-runtimes node is critical!)
    print(f"  Downloading {url} [{start}s-{end}s]...")
    dl_cmd = [
        "yt-dlp",
        "--js-runtimes", "node",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "--merge-output-format", "mp4",
        "--download-sections", f"*{start}-{end}",
        "--force-keyframes-at-cuts",
        "--no-playlist",
        "--no-warnings",
        "-o", str(tmp_raw),
        url
    ]
    rc, stdout, stderr = run_cmd(dl_cmd, timeout=90)

    if rc != 0 or not tmp_raw.exists():
        print(f"  Download FAILED: {stderr[-200:] if stderr else 'unknown error'}")
        _cleanup(tmp_raw)
        return False

    # Check raw download has audio
    has_audio, vol = check_audio(tmp_raw)
    if not has_audio:
        print(f"  Raw file has no audible audio (vol={vol}dB)")
        _cleanup(tmp_raw)
        return False

    print(f"  Raw audio: {vol:.1f}dB — encoding to 480p/30fps...")

    # Step 2: Encode to target format
    rc, _, stderr = run_cmd([
        "ffmpeg", "-y",
        "-i", str(tmp_raw),
        "-vf", "scale=-2:480",
        "-r", "30",
        "-t", "20",
        "-c:v", "libx264", "-preset", "fast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-movflags", "+faststart",
        str(output)
    ])
    _cleanup(tmp_raw)

    if rc != 0 or not output.exists():
        print(f"  Encode FAILED: {stderr[-200:] if stderr else ''}")
        return False

    # Step 3: Final verification
    has_audio, vol = check_audio(output)
    dur = get_duration(output)
    size = output.stat().st_size / 1024 / 1024

    if not has_audio:
        print(f"  FAILED final audio check")
        output.unlink()
        return False

    print(f"  OK: {size:.1f}MB, {dur:.0f}s, audio={vol:.1f}dB")
    return True


def search_and_download(name, query, description, max_attempts=5):
    """Search YouTube for a clip, try candidates until one has audio."""
    output = VIDEOS_DIR / f"{name}.mp4"

    # Skip if already good
    if output.exists():
        has_audio, vol = check_audio(output)
        if has_audio:
            dur = get_duration(output)
            size = output.stat().st_size / 1024 / 1024
            print(f"  Already OK: {size:.1f}MB, {dur:.0f}s, {vol:.1f}dB")
            return True
        else:
            print(f"  Exists but no audio — re-downloading")
            output.unlink()

    print(f"  Searching: {query}")

    # Search YouTube
    rc, stdout, stderr = run_cmd([
        "yt-dlp", "--js-runtimes", "node",
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(duration)s",
        f"ytsearch{max_attempts * 2}:{query}"
    ])

    if rc != 0:
        print(f"  Search failed: {stderr[:200]}")
        return False

    candidates = []
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            try:
                dur_f = float(parts[2])
                if 10 <= dur_f <= 600:
                    candidates.append((parts[0], parts[1], dur_f))
            except ValueError:
                continue

    for vid_id, title, dur in candidates[:max_attempts]:
        print(f"  Trying: {title[:55]}... ({dur:.0f}s)")
        tmp_raw = VIDEOS_DIR / f".{name}_raw.mp4"

        # Download first 20s (or full if short)
        dl_cmd = [
            "yt-dlp", "--js-runtimes", "node",
            "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "--merge-output-format", "mp4",
            "--no-playlist", "--no-warnings",
            "-o", str(tmp_raw),
        ]
        if dur > 25:
            dl_cmd += ["--download-sections", "*5-25", "--force-keyframes-at-cuts"]

        dl_cmd.append(f"https://www.youtube.com/watch?v={vid_id}")

        rc, _, stderr = run_cmd(dl_cmd, timeout=90)
        if rc != 0 or not tmp_raw.exists():
            print(f"    Download failed")
            _cleanup(tmp_raw)
            continue

        has_audio, vol = check_audio(tmp_raw)
        if not has_audio:
            print(f"    No audible audio ({vol}dB)")
            _cleanup(tmp_raw)
            continue

        print(f"    Audio OK ({vol:.1f}dB), encoding...")
        rc, _, _ = run_cmd([
            "ffmpeg", "-y", "-i", str(tmp_raw),
            "-vf", "scale=-2:480", "-r", "30", "-t", "20",
            "-c:v", "libx264", "-preset", "fast", "-crf", "28",
            "-c:a", "aac", "-b:a", "128k", "-ac", "2",
            "-movflags", "+faststart",
            str(output)
        ])
        _cleanup(tmp_raw)

        if rc != 0 or not output.exists():
            continue

        has_audio, vol = check_audio(output)
        if has_audio:
            size = output.stat().st_size / 1024 / 1024
            print(f"    Done: {size:.1f}MB, {vol:.1f}dB")
            return True
        else:
            output.unlink(missing_ok=True)

    return False


def _cleanup(path):
    """Remove a file and any yt-dlp partial files."""
    path = Path(path)
    path.unlink(missing_ok=True)
    # yt-dlp creates .f{N} files for separate streams
    for p in path.parent.glob(f"{path.stem}*"):
        if p.suffix not in ('.mp4',):
            p.unlink(missing_ok=True)


def main():
    check_only = "--check" in sys.argv

    print("=" * 60)
    if check_only:
        print("CHECKING existing demo videos")
    else:
        print("DOWNLOADING demo videos WITH AUDIO")
    print(f"Output: {VIDEOS_DIR}")
    print("=" * 60)

    if check_only:
        for f in sorted(VIDEOS_DIR.glob("*.mp4")):
            has_audio, vol = check_audio(f)
            dur = get_duration(f)
            size = f.stat().st_size / 1024 / 1024
            status = f"audio={vol:.1f}dB" if has_audio else "NO AUDIO"
            print(f"  {f.name}: {size:.1f}MB, {dur:.0f}s, {status}")
        return

    # Download via search (more flexible, finds diverse results)
    search_clips = [
        ("vlog_clip", "person talking vlog camera short", "Vlog — person talking to camera"),
        ("cooking_clip", "cooking kitchen sizzling sounds asmr", "Cooking with sounds"),
        ("cat_clip", "cat meowing cute funny short", "Cat with meowing"),
        ("dog_clip", "dog playing barking happy short", "Dog with barking/sounds"),
        ("street_walk", "city walk ambient sound pov", "City walk ambience"),
        ("nature_clip", "nature forest birds river sounds", "Nature ambient sounds"),
        ("music_clip", "street musician busker live performance", "Street music"),
        ("cafe_clip", "cafe coffee shop ambience sounds", "Cafe ambience"),
    ]

    results = {}
    for name, query, desc in search_clips:
        print(f"\n[{name}] {desc}")
        ok = search_and_download(name, query, desc)
        results[name] = ok
        if not ok:
            print(f"  FAILED — no suitable clip found")

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    ok_count = sum(1 for v in results.values() if v)
    print(f"\n  {ok_count}/{len(results)} clips with verified audio\n")

    for f in sorted(VIDEOS_DIR.glob("*.mp4")):
        has_audio, vol = check_audio(f)
        dur = get_duration(f)
        size = f.stat().st_size / 1024 / 1024
        status = f"audio={vol:.1f}dB" if has_audio else "NO AUDIO"
        print(f"  {f.name}: {size:.1f}MB, {dur:.0f}s, {status}")

    total = sum(f.stat().st_size for f in VIDEOS_DIR.glob("*.mp4"))
    print(f"\n  Total: {total / 1024 / 1024:.1f}MB")


if __name__ == "__main__":
    main()
