---
name: Qwen3-TTS
description: Text-to-speech generation using Qwen3-TTS via FAL API
triggers:
  - Generate speech audio from dialogue
  - Multi-character voice synthesis
  - TTS for manga dialogue
---

# Qwen3-TTS Skill

Generate high-quality speech audio from text using Qwen3-TTS.

## Usage

```python
from skills.qwen_tts import QwenTTS

tts = QwenTTS()

# Single line
result = await tts.generate_speech("Hello world!")
# result.audio_path, result.duration_seconds

# Multi-character dialogue
results = await tts.generate_dialogue([
    ("Mochi", "Hi there! What's that?"),
    ("Hero", "It's a treasure map!"),
])
```

## API

### `QwenTTS.generate_speech()`

```python
async def generate_speech(
    text: str,
    output_path: Path = None,
    voice_embedding: Optional[Path] = None,
    style_prompt: Optional[str] = None,
) -> TTSResult
```

### `QwenTTS.generate_dialogue()`

```python
async def generate_dialogue(
    dialogue_lines: list[tuple[str, str]],
    character_voices: dict[str, Path] = None,
    output_dir: Path = None,
) -> list[TTSResult]
```

## Voice Embeddings

Voice embeddings can be created using the FAL voice cloning API.
Pass a `.safetensors` file path to `voice_embedding` parameter.

## Dependencies

- FAL_KEY in .env
- requests
- ffprobe (for duration detection)
