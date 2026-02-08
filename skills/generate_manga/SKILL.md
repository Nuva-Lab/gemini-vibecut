---
name: Manga Generation
description: Generate multi-panel manga from character reference and story beats
triggers:
  - User wants to create a manga
  - User provides story beats or narrative
  - Character has been created and user wants a story
model: gemini-3-pro-image-preview (Nano Banana Pro)
---

# Manga Generation Skill

Generate sequential manga panels with visual continuity using Nano Banana Pro.

## Capabilities

- **Sequential Generation**: Panels generated in order, each using previous as reference
- **Visual Continuity**: Same colors, lighting, environment maintained across panels
- **Camera Variety**: Parses camera directions from story beats (close-up, wide, etc.)
- **Streaming Support**: Progressive display as each panel completes (~25s each)
- **Multiple Styles**: manga, webtoon, chibi, ghibli

## Input Requirements

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `character_image_path` | Path | Yes | Reference image for character consistency |
| `character_name` | str | Yes | Character name for prompts |
| `story_beats` | list[str] | Yes | 2-6 visual descriptions (one per panel) |
| `dialogues` | list[str] | No | Optional dialogue for each panel |
| `style` | str | No | Visual style (default: manga) |

## Story Beat Format

Include camera direction in story beats for best results:

```
"Close-up: Momo's eyes widen in surprise"
"Wide shot: The room is a mess of scattered toys"
"Low angle: Momo leaps heroically toward the treat"
"Medium shot: Momo lands gracefully, treat in mouth"
```

## Output

### Streaming (recommended for UI)
```python
async for event in generator.generate_manga_streaming(...):
    if event.type == 'panel':
        show_panel(event.data['image_url'])
```

### Non-streaming
```python
result = await generator.generate_manga(...)
for panel in result.panels:
    print(panel.image_url)
```

## Usage Example

```python
from skills.generate_manga.generate_manga import MangaGenerator

generator = MangaGenerator(client=gemini_client)

# Streaming (for progressive UI)
async for event in generator.generate_manga_streaming(
    character_image_path=Path("outputs/characters/momo_full_body.png"),
    character_name="Momo",
    story_beats=[
        "Wide shot: Momo spots a butterfly in the garden",
        "Medium shot: Momo crouches, ready to pounce",
        "Close-up: Momo's intense focus, whiskers twitching",
        "Low angle: Momo leaps into the air, paws extended"
    ],
    dialogues=["Ooh!", "Must... catch...", "", "GOTCHA!"],
    style="manga"
):
    if event.type == 'panel':
        # Display panel immediately
        display(event.data['image_url'])
```

## Technical Notes

- **Aspect Ratio**: 9:16 vertical (portrait orientation)
- **Generation Time**: ~25-30 seconds per panel
- **Image Chaining**: Previous panel passed as reference for continuity
- **Output Location**: `assets/outputs/manga/{manga_id}_panel_{n}.png`

## Character Consistency (Dual Anchor)

Before generating panels, Gemini Pro (`gemini-3-pro-preview`) analyzes each character reference sheet and produces a 2-3 sentence appearance description. This runs once per character (~2s), not per panel.

Each panel prompt includes **two anchors** per character:
1. **Visual reference**: Character sheet image passed as `[IMAGE N]`
2. **Text description**: `APPEARANCE: VibeCoder is an older man with long grey hair, full grey beard, black hoodie, gold headphones...`

This prevents the image model from hallucinating different characters on complex story beats.

## Visual Continuity

For panels 2+, the prompt includes:
- Previous panel as visual reference (`[IMAGE N - PREVIOUS PANEL]`)
- Explicit instructions to match colors, lighting, environment
- "NEVER replace a character with a different person or animal"

This ensures consistent backgrounds, lighting, color palette, and character identity across all panels.
