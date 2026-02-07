---
name: Final Composition
description: Concatenates video clips and optionally adds background music using FFmpeg.
triggers:
  - Video clips need concatenation
  - User wants final shareable output
keywords:
  - combine
  - finish
  - export
  - final
---

# Final Composition Skill

Concatenates video clips into final output. With Veo 3.1 native audio, this is much simpler.

## Current Use (Veo 3.1 Native Audio)

Since Veo 3.1 generates audio natively, we only need:
1. `concatenate_scenes()` - Join multiple video clips
2. `compose_video_with_music()` - Add optional background music

## When to Use

- Video and music are ready → Combine into final
- Need to add text overlays
- Need to concatenate multiple scenes
- Preparing for export/sharing

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `video_path` | Path | Yes | — | Path to video file |
| `audio_path` | Path | No | None | Path to audio/music file |
| `output_name` | str | No | Auto-generated | Output filename |
| `music_volume` | float | No | 0.3 | Background music volume (0-1) |

### Additional Operations

| Operation | Method | Description |
|-----------|--------|-------------|
| `add_text_overlay` | `execute_with_text()` | Add text to video |
| `concatenate` | `concatenate_scenes()` | Join multiple videos |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `output_path` | Path | Path to final composed video |
| `metadata` | dict | Composition metadata |

## Implementation Contract

```python
class VideoComposer:
    async def execute(
        self,
        video_path: Path,
        audio_path: Path = None,
        output_name: str = None,
        music_volume: float = 0.3
    ) -> tuple[Path, dict]:
        """
        Compose video with audio.

        Raises:
            FileNotFoundError: If video_path doesn't exist
            FFmpegError: If composition fails
        """
        ...

    async def concatenate_scenes(
        self,
        scene_paths: list[Path],
        output_name: str = None
    ) -> Path:
        """Concatenate multiple video scenes."""
        ...

    async def add_text_overlay(
        self,
        video_path: Path,
        text: str,
        position: str = "bottom"
    ) -> Path:
        """Add text overlay to video."""
        ...
```

## Example Usage

```python
from skills.compose_final import VideoComposer

skill = VideoComposer()

# Basic: combine video + music
final_path, metadata = await skill.execute(
    video_path=Path("scene.mp4"),
    audio_path=Path("bgm.mp3")
)

# With custom settings
final_path, metadata = await skill.execute(
    video_path=video_path,
    audio_path=music_path,
    output_name="my_creation",
    music_volume=0.4
)

# Concatenate scenes
final_path = await skill.concatenate_scenes(
    scene_paths=[scene1, scene2, scene3],
    output_name="full_story"
)

# Add text
with_text = await skill.add_text_overlay(
    video_path=final_path,
    text="Created with Creative Universe",
    position="bottom"
)
```

## Full Pipeline Example

```python
# Complete creative pipeline
pet_analysis = await understand_skill.execute(pet_photo, "pet")
world_analysis = await understand_skill.execute(scene_photo, "world")

character, _ = await character_skill.execute(pet_analysis)

video_path, _ = await video_skill.execute(
    characters=[character],
    world=world_analysis
)

music_path, _ = await music_skill.execute(
    scene_description="Character explores world",
    mood="adventurous",
    duration=10
)

final_path, _ = await compose_skill.execute(
    video_path=video_path,
    audio_path=music_path,
    output_name="my_universe"
)
```

## Dependencies

- FFmpeg (system binary)
- Generated video files
- Generated audio files

## FFmpeg Commands Used

### Basic Operations

```bash
# Combine video + audio (when video HAS audio track)
ffmpeg -i video.mp4 -i audio.mp3 \
  -filter_complex "[1:a]volume=0.3[music];[0:a][music]amix=inputs=2:duration=first[aout]" \
  -map 0:v -map "[aout]" \
  -c:v copy -c:a aac \
  output.mp4

# Concatenate scenes (same codec, no re-encode)
ffmpeg -f concat -safe 0 -i list.txt \
  -c copy output.mp4

# Add text overlay
ffmpeg -i video.mp4 \
  -vf "drawtext=text='Hello':fontsize=48:fontcolor=white:x=(w-tw)/2:y=h-th-50" \
  output.mp4
```

### Audio-Video Sync Commands (KEY!)

```bash
# 1. Get audio duration (ffprobe)
ffprobe -v error \
  -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  audio.wav
# Output: 2.345 (seconds)

# 2. Pad audio to target duration (extend with silence)
ffmpeg -y -i audio.wav \
  -af "apad=whole_dur=3.5" \
  -c:a pcm_s16le \
  padded.wav
# apad=whole_dur=X pads to exactly X seconds

# 3. Add audio to SILENT video (Veo videos have no audio track)
ffmpeg -y \
  -i silent_video.mp4 \
  -i audio.wav \
  -c:v copy \
  -c:a aac \
  -map 0:v:0 \
  -map 1:a:0 \
  -t 3.5 \
  output.mp4
# -map 0:v:0 = video from first input
# -map 1:a:0 = audio from second input
# -t X = force exact duration (cuts if longer)

# 4. Concatenate pre-synced clips
echo "file 'clip1_synced.mp4'" > concat.txt
echo "file 'clip2_synced.mp4'" >> concat.txt
echo "file 'clip3_synced.mp4'" >> concat.txt
ffmpeg -f concat -safe 0 -i concat.txt -c copy final.mp4
```

### Why `-map` Instead of `-amix`?

```bash
# ❌ FAILS on Veo videos (no audio track to mix)
ffmpeg -i veo_video.mp4 -i audio.wav \
  -filter_complex "[0:a][1:a]amix=inputs=2" ...
# Error: Stream #0 has no audio

# ✅ WORKS - explicitly map video and audio streams
ffmpeg -i veo_video.mp4 -i audio.wav \
  -map 0:v:0 -map 1:a:0 ...
```

## Audio-Video Sync Patterns

**CRITICAL:** When combining multi-segment video with multi-segment audio, use per-clip sync.

### ❌ WRONG: Separate Concatenation
```python
# DON'T DO THIS - causes sync drift
video_clips = [v1, v2, v3]  # 3 clips (one failed)
audio_clips = [a1, a2, a3, a4]  # 4 clips

concat_video = concatenate(video_clips)  # 3 clips
concat_audio = concatenate(audio_clips)  # 4 clips
final = combine(concat_video, concat_audio)  # MISMATCH!
```

### ✅ RIGHT: Per-Clip Audio Overlay
```python
# DO THIS - guarantees sync
synced_clips = []
for i, (video, audio, duration) in enumerate(zip(videos, audios, durations)):
    if video is None:
        continue  # Skip failed clips (and their audio!)

    # Pad audio if shorter than video
    if get_duration(audio) < duration:
        audio = pad_audio(audio, duration)

    # Overlay audio onto THIS clip
    synced = add_audio_to_clip(video, audio, duration)
    synced_clips.append(synced)

# Now concatenate pre-synced clips
final = concatenate(synced_clips)  # Perfect sync!
```

### Key Methods for Sync

| Method | Purpose |
|--------|---------|
| `add_audio_to_clip()` | Add audio to single video clip with padding |
| `pad_audio_to_duration()` | Extend audio with silence using `apad` filter |
| `_get_audio_duration()` | Get exact audio duration via `ffprobe` |

### Veo Video Note
Veo 3.1 generates **silent videos** (no audio track). Always use `add_audio_to_clip()` or `add_audio_to_video()` - never `amix` filter which requires existing audio track.

---

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `FileNotFoundError` | Input file missing | Check paths exist |
| `FFmpegError` | FFmpeg command failed | Check FFmpeg installed, check input formats |
| `PermissionError` | Can't write output | Check output directory permissions |

## Requirements

- FFmpeg must be installed: `brew install ffmpeg` (macOS)
- Write permissions to output directory
