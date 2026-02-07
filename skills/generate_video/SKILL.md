---
name: Video Generation
description: Generates animated video using Veo 3.1 multi-image reference mode with native audio. No TTS needed.
triggers:
  - User wants to see characters animated
  - Manga panels ready for animation
  - Agent has characters and panels ready
keywords:
  - animate
  - video
  - scene
  - make it move
---

# Video Generation Skill

Creates animated video clips using Veo 3.1 multi-image reference mode with native audio.

**Docs:** https://ai.google.dev/gemini-api/docs/video?example=dialogue#reference-images

## API Mode: Multi-Image References

Uses `reference_images` parameter (NOT `image` parameter). This is text-to-video with visual references for consistency.

| Constraint | Value | Notes |
|------------|-------|-------|
| Max references | **3** | API enforced limit |
| Duration | Optional | API handles default (~8s) |
| `image` param | **NOT USED** | Incompatible with reference_images |
| Models | Both work | `veo-3.1-generate-preview` or `veo-3.1-fast-generate-preview` |

## Reference Strategy

| Slot | Image | Purpose |
|------|-------|---------|
| 1 | Panel image | Scene composition |
| 2 | Character 1 sheet | Character consistency |
| 3 | Character 2 sheet | Second character (optional) |

## Method Signature

```python
async def generate_clip_with_references(
    self,
    keyframe_path: Path,              # Panel as reference #1
    reference_images: list[Path],      # Character sheets (refs #2-3)
    dialogue: str = None,              # For native audio
    story_context: str = None,         # Scene description
    character_name: str = None,        # Speaker name
    duration_seconds: int = None,      # Optional (default: 8)
    clip_index: int = 0,
    next_panel_path: Path = None,      # Ignored (incompatible with refs)
) -> VideoClipResult:
```

## Native Audio Prompting

Veo 3.1 generates speech from dialogue in the prompt:

```
DIALOGUE:
Mochi says: "Wow, this is amazing!"

AUDIO:
- Character speaks the dialogue naturally with appropriate emotion
- Natural ambient sounds matching the scene
```

## Example Usage

```python
from skills.generate_video import VideoGenerator

video_gen = VideoGenerator()

result = await video_gen.generate_clip_with_references(
    keyframe_path=panel_path,
    reference_images=[character_sheet_1, character_sheet_2],
    dialogue="Mochi: Look at this treasure map!",
    story_context="SCENE 1: Mochi discovers a mysterious map",
    character_name="Mochi",
)

# Video has native audio - no FFmpeg overlay needed!
print(f"Generated: {result.video_path} ({result.duration_seconds}s)")
```

## API Call (Internal)

```python
# NO image= param when using reference_images
operation = client.models.generate_videos(
    model="veo-3.1-fast-generate-preview",
    prompt=prompt,  # Includes dialogue for native audio
    config=types.GenerateVideosConfig(
        reference_images=[panel_ref, char1_ref, char2_ref],
        aspect_ratio="9:16",
    ),
)
```

## Aspect Ratio

| Ratio | Use Case |
|-------|----------|
| `9:16` | TikTok, Reels, Shorts, Manga (default) |
| `16:9` | YouTube horizontal |

## Polling & Timeout

- Poll interval: 10 seconds
- Max wait: 5 minutes (300s)
- Typical generation: 30-60 seconds

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `400 INVALID_ARGUMENT` | >3 refs or `image`+`reference_images` | Check ref count |
| `FileNotFoundError` | Panel/ref missing | Check paths |
| `TimeoutError` | Veo too slow | Retry |
