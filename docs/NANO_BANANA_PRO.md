# Nano Banana Pro API Reference

> **Model ID:** `gemini-3-pro-image-preview`
>
> State-of-the-art image generation optimized for professional asset production.

## Capabilities

| Feature | Value |
|---------|-------|
| **Max Resolution** | 4K (1K, 2K, 4K options) |
| **Reference Images** | Up to 14 (6 objects + 5 humans + 3 flex) |
| **Output** | Text + multiple images (interleaved) |
| **Thinking Mode** | Yes - generates interim "thought images" |
| **Google Search Grounding** | Yes |
| **Advanced Text Rendering** | Yes |

## Aspect Ratios

`1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`

## Python SDK Usage

### Basic Generation

```python
from google import genai
from google.genai import types

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=["A cute anime cat character"],
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
        image_config=types.ImageConfig(
            aspect_ratio="3:4",
            image_size="2K"
        )
    )
)

for part in response.parts:
    if part.text:
        print(part.text)
    elif image := part.as_image():
        image.save("output.png")
```

### With Reference Images

```python
from PIL import Image

reference = Image.open("source_photo.jpg")

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=[
        reference,
        "Create an anime version of this pet, maintaining their distinctive features."
    ],
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
        image_config=types.ImageConfig(
            aspect_ratio="3:4",
            image_size="2K"
        )
    )
)
```

### Multiple Reference Images

```python
from PIL import Image

ref1 = Image.open("pet_photo_1.jpg")
ref2 = Image.open("pet_photo_2.jpg")
ref3 = Image.open("pet_photo_3.jpg")

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=[
        ref1, ref2, ref3,
        "Using these reference photos, create a consistent anime character."
    ],
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
        image_config=types.ImageConfig(
            image_size="2K"
        )
    )
)
```

### Interleaved Multi-Image Output

Request multiple images in one call:

```python
prompt = """
Generate a character sheet with THREE images:
1. Full body standing pose
2. Close-up portrait
3. Expression sheet (happy, sad, surprised)
"""

response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=[reference_image, prompt],
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
        image_config=types.ImageConfig(image_size="2K")
    )
)

# Process multiple images from response
images = []
for part in response.parts:
    if image := part.as_image():
        images.append(image)
```

## Prompt Best Practices

### DO: Write Narrative Descriptions

```
A warm, expressive anime-style orange tabby cat character with bright
green eyes, soft fur, and a friendly demeanor. Standing in a 3/4 pose,
tail curled playfully, with a subtle smile. Clean cel-shaded style
suitable for animation, on a soft gradient background.
```

### DON'T: Use Keyword Lists

```
orange cat, anime, cute, standing, green eyes
```

### Prompt Templates

**Character from Photo:**
```
Using the attached reference photo, create an anime character.

The character should capture these key features:
- [Physical feature 1 from Gemini analysis]
- [Physical feature 2]
- [Distinctive markings]

Personality: [traits from concept]
Art style: [style name]
Pose: [pose description]

Clean lines suitable for animation, [background type] background.
```

**Character Sheet (Multi-Image):**
```
Create a character sheet for this [pet type].

Generate [N] images:
1. Full body: standing pose, 3/4 angle
2. Portrait: close-up, expressive eyes
3. [Additional variant]

All images should:
- Capture distinctive features from reference
- Maintain consistent [style] anime style
- Have clean lines for animation
```

## Important Notes

- **Resolution**: Always uppercase `"2K"` not `"2k"`
- **SynthID**: All images include invisible watermark
- **Rate Limits**: Be mindful of API quotas
- **Thought Images**: Response may include interim thought images (check `part.thought`)

## Error Handling

```python
import time
from google.api_core import exceptions

def generate_with_retry(client, model, contents, config, max_retries=3):
    """Generate content with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except exceptions.ResourceExhausted as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
        except exceptions.InvalidArgument as e:
            print(f"Invalid argument: {e}")
            raise
```

## References

- [Official Docs](https://ai.google.dev/gemini-api/docs/image-generation)
- [Imagen Overview](https://ai.google.dev/gemini-api/docs/imagen)
