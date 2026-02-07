---
name: Image Understanding
description: Analyzes photos to extract structured information about pets, people, or world settings using Gemini 3 multimodal capabilities.
triggers:
  - User uploads an image
  - Agent needs to understand visual content
keywords:
  - analyze
  - understand
  - what is this
  - look at
---

# Image Understanding Skill

Analyzes uploaded images and extracts structured information that can be used for character creation or world building.

## When to Use

- User uploads a photo of their pet → Extract features, personality traits
- User uploads a selfie → Extract style, aesthetic for anime character
- User uploads a scene photo → Extract mood, setting, visual style for world building

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `image_path` | Path | Yes | — | Path to the image file |
| `analysis_type` | str | No | "auto" | One of: "pet", "person", "world", "auto" |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `analysis` | dict | Structured analysis with type-specific fields |

### Output Schema by Type

**Pet Analysis:**
```json
{
  "species": "dog",
  "breed_guess": "golden retriever",
  "physical_features": {
    "coat_color": "golden",
    "eye_color": "brown",
    "distinctive_features": ["fluffy ears"]
  },
  "personality_traits": ["playful", "friendly"],
  "suggested_character_archetype": "loyal companion"
}
```

**Person Analysis:**
```json
{
  "hair": {"color": "black", "style": "short"},
  "fashion_aesthetic": "casual modern",
  "expression_mood": "confident",
  "suggested_anime_traits": ["protagonist energy"],
  "suggested_character_archetype": "determined hero"
}
```

**World Analysis:**
```json
{
  "setting_type": "cyberpunk city",
  "visual_style": {
    "color_palette": "neon and dark",
    "lighting": "dramatic",
    "evoked_style": "blade runner"
  },
  "atmosphere": "mysterious",
  "mood_keywords": ["futuristic", "lonely", "electric"]
}
```

## Implementation Contract

```python
class ImageUnderstanding:
    async def execute(
        self,
        image_path: Path,
        analysis_type: str = "auto"
    ) -> dict:
        """
        Analyze an image and return structured information.

        Raises:
            FileNotFoundError: If image_path doesn't exist
            ValueError: If analysis_type is invalid
            APIError: If Gemini API call fails
        """
        ...
```

## Example Usage

```python
from skills.understand_image import ImageUnderstanding

skill = ImageUnderstanding()

# Auto-detect type
result = await skill.execute(image_path=Path("photo.jpg"))

# Specify type for better results
result = await skill.execute(
    image_path=Path("my_dog.jpg"),
    analysis_type="pet"
)
```

## Dependencies

- Gemini 3 Flash/Pro API (multimodal)
- Pillow (image loading)

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `FileNotFoundError` | Image path invalid | Check path exists |
| `ValueError` | Invalid analysis_type | Use "pet", "person", "world", or "auto" |
| `APIError` | Gemini API failure | Retry with backoff |
