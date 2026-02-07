---
name: Character Generation
description: Generates anime character images from photo analysis using Nano Banana Pro (gemini-3-pro-image-preview). Creates character sheets with full body and portrait views at 2K resolution.
triggers:
  - User wants to create a character from their pet/photo
  - Agent has completed image analysis and needs to generate visuals
keywords:
  - create character
  - make anime
  - character card
  - character sheet
---

# Character Generation Skill

Transforms image analysis into anime character artwork using Nano Banana Pro (`gemini-3-pro-image-preview`).

## Key Features

- **2K Resolution Output** - High quality images suitable for production
- **Reference Image Support** - Uses source photo to maintain visual consistency
- **Interleaved Output** - Generates multiple images (full body + portrait) in a single API call
- **Retry Logic** - Handles rate limits with exponential backoff

## When to Use

- After `understand_image` has analyzed a pet photo → Generate anime pet character
- After `understand_image` has analyzed a person photo → Generate anime alter-ego
- User explicitly requests character creation

## ⚠️ Critical: Single Subject Identification Across Multiple Images

When user provides 3+ reference images for character creation, each image may contain **multiple subjects** (e.g., two dogs, person with pet, etc.).

**The key capability:** Both Gemini 3 and Nano Banana Pro can **reason across multiple images** to identify the SAME entity appearing in all of them.

### How It Works

```
Image 1: Golden retriever + person in background
Image 2: Golden retriever + another dog
Image 3: Golden retriever sleeping alone
                    ↓
    Gemini identifies: "The golden retriever appears in all 3 images"
                    ↓
    Character sheet generated for: ONE golden retriever
```

### Implementation Requirements

1. **Reference Image Analysis**: When multiple images are provided, use Gemini 3's long context to:
   - Identify which subject appears CONSISTENTLY across all images
   - Distinguish between "main subject" vs "background entities"
   - Note visual characteristics that confirm same identity (color, markings, features)

2. **Prompt Engineering**: Include explicit instructions like:
   ```
   "These reference images all contain the same [pet/person].
   Identify the consistent subject across all images and generate
   a character sheet for ONLY that subject, ignoring other entities
   that may appear in individual images."
   ```

3. **Generation Focus**: When calling Nano Banana Pro:
   - Pass all reference images for consistency
   - Explicitly specify which subject to focus on
   - Request single-subject character sheet output

### Anti-Pattern

```
❌ WRONG: Generate character from each subject in each image
   → Results in multiple characters when user wanted ONE

✅ RIGHT: Reason across images to find consistent subject
   → One character sheet for the entity that appears in ALL images
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `analysis` | dict | Yes | — | Output from `understand_image` skill |
| `name` | str | No | Auto-generated | Character name |
| `style` | str | No | "anime" | Visual style (see options below) |
| `variants` | list | No | ["full_body"] | Which views to generate |

### Style Options

| Style | Description |
|-------|-------------|
| `anime` | Standard anime style |
| `studio_ghibli` | Soft, painterly Ghibli aesthetic |
| `cyberpunk_anime` | Neon-lit, high-tech anime |
| `watercolor_anime` | Soft watercolor anime blend |
| `chibi` | Cute, super-deformed style |

### Variant Options

| Variant | Description |
|---------|-------------|
| `full_body` | Full body, standing pose |
| `portrait` | Head and shoulders |
| `expressions` | Expression sheet (happy, sad, angry, surprised) |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `character` | Character | Character object with metadata |
| `images` | dict[str, Path] | Generated images by variant |

### Character Object Schema

```python
Character(
    id="abc123",
    name="Mochi",
    source_type="pet",
    style="anime",
    analysis={...},      # Original analysis
    concept={...},       # Generated character concept
    generated_images={
        "full_body": Path("..."),
        "portrait": Path("...")
    }
)
```

## Implementation Contract

```python
class CharacterGenerator:
    async def generate_character_sheet(
        self,
        character: Character,
    ) -> dict[str, Path]:
        """
        Generate full character sheet (multiple views) in ONE API call.

        Uses Nano Banana Pro's interleaved output capability to generate
        both full_body and portrait images in a single request.

        Args:
            character: Character object with analysis/concept populated

        Returns:
            Dict mapping variant names to file paths:
            {
                "full_body": Path("..."),
                "portrait": Path("...")
            }
        """
        ...

    async def generate_character_image(
        self,
        character: Character,
        variant: str = "full_body",
    ) -> Optional[Path]:
        """Generate a single character image variant."""
        ...
```

## Example Usage

```python
from skills.generate_character import CharacterGenerator
from models.character import Character
from pathlib import Path

# Initialize
gen = CharacterGenerator()

# Create character with analysis and concept
character = Character(
    name="Mochi",
    source_image=Path("assets/demo_photos/pets/cat_01.webp"),
    source_type="pet",
    style="anime",
    analysis=pet_analysis,
    concept=pet_concept,
)

# Generate full character sheet (full_body + portrait)
images = await gen.generate_character_sheet(character)
# Returns: {"full_body": Path("..."), "portrait": Path("...")}

# Or generate a single variant
portrait_path = await gen.generate_character_image(character, variant="portrait")
```

## Dependencies

- Nano Banana Pro API (image generation)
- `understand_image` skill (provides input)

## Progressive Disclosure

| Level | What User Specifies | What's Auto-Generated |
|-------|---------------------|----------------------|
| 0 | Just `analysis` | Name, style, single full_body |
| 1 | `analysis` + `name` + `style` | Variants |
| 2 | Everything | Nothing |

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `ValueError` | Empty or invalid analysis | Run `understand_image` first |
| `APIError` | Nano Banana failure | Retry with backoff |
| `StyleError` | Unknown style | Use supported style |
