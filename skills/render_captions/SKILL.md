---
name: Caption Renderer
description: Burn karaoke captions into video using FFmpeg ASS subtitles (~20s for 16s video)
triggers:
  - Add captions to video
  - Karaoke subtitle overlay
  - Rolling lyrics on video
---

# Caption Renderer Skill

Burn karaoke-style rolling captions into video using FFmpeg ASS subtitles.

Words start **white** (not yet sung) and fill to **gold** as the karaoke sweep passes.
Automatically scales to 1080x1920 if input is lower resolution (e.g., Veo's 720x1280).

Performance: ~20s for 16s video at 720x1280 input, ~40s with scale to 1080x1920.

## Usage

```python
from skills.render_captions import CaptionRenderer, CaptionSegment, WordSegment

renderer = CaptionRenderer()

# Create captions with word-level timing
captions = [
    CaptionSegment(
        text="Hello world!",
        startMs=0,
        endMs=2000,
        speaker="Mochi",
        words=[
            WordSegment("Hello", 0, 800),
            WordSegment("world!", 900, 2000),
        ],
    ),
]

# Render video with captions (auto-scales to 1080x1920)
output = await renderer.render_with_captions(
    video_path=Path("video.mp4"),
    captions=captions,
)
```

## Multi-Clip Rendering

```python
# Render multiple clips with per-clip captions
output = await renderer.render_concatenated_video(
    clip_paths=[clip1, clip2, clip3],
    clip_captions=[captions1, captions2, captions3],
    audio_paths=[audio1, audio2, audio3],
)
```

## How It Works

1. Generates ASS subtitle file at target resolution (1080x1920)
2. Uses `\k` karaoke tags for word-level gold highlighting
3. FFmpeg `subtitles=` filter burns captions in a single pass
4. Optional `scale=` filter normalizes resolution in the same pass

## Dependencies

- FFmpeg (with libass for subtitle rendering)

## Style

- Font: Noto Sans Bold, 56px
- Colors: White (unseen) → Gold (#FFD700) as words are sung
- Background: Black semi-transparent box (BorderStyle=3)
- Position: Bottom-centered, 120px margin from bottom edge
