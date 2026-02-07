---
name: Caption Renderer
description: Render video with rolling karaoke captions using Remotion
triggers:
  - Add captions to video
  - Karaoke subtitle overlay
  - Motion graphics for dialogue
---

# Caption Renderer Skill

Render video with rolling karaoke-style captions using Remotion.

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

# Render video with captions
output = await renderer.render_with_captions(
    video_path=Path("video.mp4"),
    captions=captions,
    audio_path=Path("dialogue.wav"),
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

## Dependencies

- Remotion (`cd remotion && npm install`)
- FFmpeg (for concatenation)
- Node.js 18+

## Setup

```bash
cd remotion
npm install
```
