---
name: Music Generation
description: Generates original background music using Google's Music Generation API. Creates soundtracks matched to scene mood and timing.
triggers:
  - Video has been generated and needs soundtrack
  - User wants background music for their creation
keywords:
  - music
  - soundtrack
  - BGM
  - audio
---

# Music Generation Skill

Creates original background music that matches the mood and pacing of video scenes.

## When to Use

- After video generation → Add matching soundtrack
- User wants custom music for their scene
- Need to set emotional tone with audio

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `scene_description` | str | Yes | — | What's happening in the scene |
| `mood` | str | Yes | — | Emotional tone (see options) |
| `duration` | int | No | 30 | Duration in seconds |
| `style` | str | No | "anime_orchestral" | Music style |

### Mood Options

| Mood | Description |
|------|-------------|
| `adventurous` | Upbeat, exciting, forward momentum |
| `melancholic` | Sad, reflective, bittersweet |
| `mysterious` | Intriguing, suspenseful, curious |
| `joyful` | Happy, celebratory, light |
| `epic` | Grand, powerful, dramatic |
| `peaceful` | Calm, serene, gentle |

### Style Options

| Style | Description |
|-------|-------------|
| `anime_orchestral` | Classic anime soundtrack feel |
| `lofi_chill` | Relaxed, lo-fi hip hop vibe |
| `cinematic_epic` | Big movie trailer sound |
| `cute_playful` | Light, bouncy, kawaii |
| `electronic_ambient` | Atmospheric synths |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `audio_path` | Path | Path to generated audio file |
| `duration` | float | Actual audio duration |
| `metadata` | dict | Generation metadata |

## Implementation Contract

```python
class MusicGenerator:
    async def execute(
        self,
        scene_description: str,
        mood: str,
        duration: int = 30,
        style: str = "anime_orchestral"
    ) -> tuple[Path, dict]:
        """
        Generate background music for a scene.

        Raises:
            ValueError: If mood or style is invalid
            APIError: If Music API call fails
        """
        ...
```

## Example Usage

```python
from skills.generate_music import MusicGenerator

skill = MusicGenerator()

# Basic usage
audio_path, metadata = await skill.execute(
    scene_description="Two characters explore a neon-lit city",
    mood="adventurous"
)

# Full control
audio_path, metadata = await skill.execute(
    scene_description="Peaceful morning in a meadow",
    mood="peaceful",
    duration=45,
    style="anime_orchestral"
)
```

## Integration with Video

```python
# Generate music to match video
video_path, video_meta = await video_skill.execute(...)

music_path, music_meta = await music_skill.execute(
    scene_description=scene_concept["scene_description"],
    mood=scene_concept["mood_for_music"],
    duration=video_meta["duration"]
)

# Compose together
final = await compose_skill.execute(
    video=video_path,
    audio=music_path
)
```

## Dependencies

- Google Music Generation API
- Scene concept (for mood extraction)

## API Reference

See: https://ai.google.dev/gemini-api/docs/music-generation

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `ValueError` | Invalid mood/style | Use supported option |
| `APIError` | Music API failure | Retry with backoff |
| `DurationError` | Duration out of range | Use 5-120 seconds |
