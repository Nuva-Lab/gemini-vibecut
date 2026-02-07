---
name: TTS Generation
description: Generates speech audio from dialogue using Gemini TTS. Supports multi-speaker conversations with consistent voices per character.
triggers:
  - Story panels have dialogue that needs to be voiced
  - Agent needs audio for video generation
keywords:
  - text to speech
  - voice
  - dialogue
  - audio
---

# TTS Generation Skill

Converts panel dialogue into speech audio using Gemini TTS (`gemini-2.5-flash-preview-tts`).

## Key Features

- **Multi-speaker support**: Up to 2 distinct voices per conversation
- **Consistent character voices**: Same voice for same character across all clips
- **Duration tracking**: Returns exact audio duration for Veo sync
- **Expressive speech**: Control tone through natural language prompts

## When to Use

- After manga generation, to voice the dialogue for each panel
- Before Veo video generation (need audio duration first)
- When creating animated stories with character conversations

## Audio Format

| Parameter | Value |
|-----------|-------|
| Sample Rate | 24000 Hz |
| Channels | 1 (mono) |
| Sample Width | 2 bytes (16-bit) |
| Format | WAV (PCM) |

## Available Voices

| Voice | Style | Good For |
|-------|-------|----------|
| Kore | Firm | Confident characters |
| Puck | Upbeat | Cheerful characters |
| Charon | Informative | Narration |
| Fenrir | Excitable | Energetic pets |
| Aoede | Breezy | Calm characters |
| Zephyr | Bright | Young characters |
| Leda | Youthful | Kids, cute pets |
| Sulafat | Warm | Friendly characters |

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `dialogue` | str | Yes | — | The dialogue text to voice |
| `character_name` | str | Yes | — | Character speaking (for multi-speaker) |
| `voice_name` | str | No | Auto-select | Specific voice to use |
| `emotion` | str | No | "neutral" | Emotion hint (cheerful, sad, excited) |

### Multi-Speaker Input

For conversations between 2 characters:

```python
dialogues = [
    {"character": "Mochi", "text": "Hi there!", "emotion": "cheerful"},
    {"character": "Hero", "text": "Hey Mochi!", "emotion": "excited"},
]
```

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `audio_path` | Path | Path to generated WAV file |
| `duration_seconds` | float | Exact audio duration |
| `voice_used` | str | Voice name that was used |

## Implementation Contract

```python
@dataclass
class TTSResult:
    audio_path: Path
    duration_seconds: float
    voice_used: str
    character_name: str

class TTSGenerator:
    async def generate_dialogue(
        self,
        dialogue: str,
        character_name: str,
        voice_name: str = None,
        emotion: str = "neutral",
    ) -> TTSResult:
        """
        Generate speech for a single character's dialogue.

        Args:
            dialogue: Text to speak
            character_name: Who is speaking
            voice_name: Specific voice (or auto-select)
            emotion: Emotional tone hint

        Returns:
            TTSResult with audio path and duration
        """
        ...

    async def generate_conversation(
        self,
        dialogues: list[dict],
        voice_mapping: dict[str, str] = None,
    ) -> list[TTSResult]:
        """
        Generate speech for a multi-character conversation.

        Maintains voice consistency across the conversation.
        Max 2 speakers per call (Gemini TTS limit).

        Args:
            dialogues: List of {character, text, emotion} dicts
            voice_mapping: Optional {character_name: voice_name} mapping

        Returns:
            List of TTSResult, one per dialogue line
        """
        ...

    async def generate_panel_audio(
        self,
        panel_dialogues: list[str],
        character_names: list[str],
        voice_mapping: dict[str, str] = None,
    ) -> tuple[Path, float]:
        """
        Generate combined audio for a single manga panel.

        Multiple characters speaking in one panel get combined
        into a single audio file.

        Returns:
            (combined_audio_path, total_duration_seconds)
        """
        ...
```

## Example Usage

```python
from skills.generate_tts import TTSGenerator

tts = TTSGenerator()

# Single dialogue
result = await tts.generate_dialogue(
    dialogue="Let's go on an adventure!",
    character_name="Mochi",
    emotion="excited"
)
print(f"Audio: {result.audio_path}, Duration: {result.duration_seconds}s")

# Multi-character conversation
results = await tts.generate_conversation(
    dialogues=[
        {"character": "Mochi", "text": "What's that?", "emotion": "curious"},
        {"character": "Hero", "text": "It's a treasure map!", "emotion": "excited"},
    ],
    voice_mapping={
        "Mochi": "Leda",   # Youthful voice for pet
        "Hero": "Kore",    # Firm voice for protagonist
    }
)
```

## Voice Selection Strategy

When no voice is specified, auto-select based on character analysis:

| Character Type | Suggested Voice | Why |
|----------------|-----------------|-----|
| Pet (cat/dog) | Leda / Fenrir | Youthful, excitable |
| Child | Zephyr / Leda | Bright, youthful |
| Adult male | Kore / Charon | Firm, informative |
| Adult female | Aoede / Sulafat | Breezy, warm |

## Integration with Video Pipeline

```
Panel Dialogue → TTS → duration_seconds → Veo (duration param)
                  ↓
             audio_path → FFmpeg (combine with video)
```

The duration from TTS drives Veo video length to ensure sync.

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `ValueError` | Empty dialogue | Skip or use placeholder |
| `APIError` | TTS API failure | Retry with backoff |
| `VoiceError` | Unknown voice name | Fall back to default |
