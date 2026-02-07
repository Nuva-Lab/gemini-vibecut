---
name: Animated Story Generation
description: "Full pipeline from manga panels to animated video. Two audio modes: dialogue (Qwen3-TTS + karaoke captions) or music (ElevenLabs + rolling lyrics)."
triggers:
  - Manga panels ready for animation
  - User wants video from manga/story
  - Story needs to become animated
  - Add music to video
keywords:
  - animate manga
  - video from story
  - make video
  - animate story
  - background music
  - song lyrics
---

# Animated Story Generation Skill

Orchestrates the complete pipeline from manga panels to final video. Supports two audio modes:
- **Dialogue mode**: Qwen3-TTS + word-level karaoke captions
- **Music mode**: ElevenLabs cloud song generation + rolling lyrics

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MANGA PANELS (4 panels with dialogue)                                   │
│  Panel 1: "Mochi: Hi!"  Panel 2: "Hero: Wow!"  Panel 3: "Mochi: Look!"  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  QWEN3-TTS (VoiceDesign → Clone)                    skills/qwen_tts/    │
│  - Design voice per character from persona (once)                       │
│  - Clone prompt for consistent timbre across all lines                  │
│  - Modes: torch (recommended) / local (mlx) / cloud (FAL)              │
│  - Returns: audio.wav + duration per panel                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  QWEN3-FORCEDALIGNER (~30ms precision)                                  │
│  - Align text to audio → word timestamps                                │
│  - Returns: [{text, startMs, endMs}, ...] per word                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  VEO 3.1 (4s minimal motion clips)                                      │
│  - Each panel → 4s animated clip with subtle motion                     │
│  - Silent video (no Veo audio)                                          │
│  - Fast model for dev, regular for production                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  FFMPEG (merge audio + video)                                           │
│  - Add TTS audio to each silent clip                                    │
│  - Pad audio if shorter than video                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  REMOTION (motion graphics)                                             │
│  - Render karaoke-style rolling captions                                │
│  - Word-by-word highlight synced to audio                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  FINAL OUTPUT                                                           │
│  - 4 clips × 4s = 16s video                                             │
│  - TTS dialogue audio (consistent character voices)                     │
│  - Karaoke captions synced to speech                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Usage

### Recommended: Torch TTS with VoiceDesign → Clone

```python
from skills.generate_animated_story import AnimatedStoryGenerator

gen = AnimatedStoryGenerator()

async for event in gen.generate_animated_story_with_dialogue_streaming(
    manga_result=manga_result,
    character_personas={
        "Mochi": "A cheerful young girl with a high-pitched, excited tone",
        "Hero": "A brave young man with a confident, warm baritone voice",
    },
    enable_captions=True,
    language="English",
    tts_mode="torch",  # VoiceDesign → Clone (consistent voices)
):
    if event.type == 'tts_progress':
        print(f"TTS: {event.data['message']}")
    elif event.type == 'complete':
        print(f"Video: {event.data['final_video_path']}")
```

### Basic (no dialogue/captions)

```python
async for event in gen.generate_animated_story_streaming(
    manga_result=manga_result,
    clip_duration=4,
):
    if event.type == 'complete':
        print(f"Video: {event.data['final_video_path']}")
```

## TTS Modes

| Mode | How it works | Voice consistency | Speed |
|------|-------------|-------------------|-------|
| `torch` | VoiceDesign → Clone via `qwen_tts` package | Best (cached prompt) | ~10s/line on MPS |
| `local` | mlx_audio VoiceDesign per-line | Poor (varies each call) | ~5s/line on MLX |
| `cloud` | FAL API predefined voices | Good (fixed speakers) | ~3s/line |

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `manga_result` | MangaResult | Yes | Output from MangaGenerator |
| `character_personas` | dict[str, str] | No | Persona instructions for voice design |
| `character_voices` | dict[str, str] | No | Predefined voice names (cloud mode) |
| `music_path` | Path | No | Optional background music |
| `clip_duration` | int | No | 4, 6, or 8 seconds (default: 4) |
| `enable_captions` | bool | No | Render karaoke captions (default: True) |
| `language` | str | No | 'English' or 'Chinese' (default: English) |
| `tts_mode` | str | No | 'torch', 'local', 'cloud', or 'auto' (default: auto) |

## Stream Events

| Event Type | Data | Description |
|------------|------|-------------|
| `start` | story_id, mode | Pipeline started |
| `tts_progress` | panel_index, message | TTS generation progress |
| `align_progress` | message | Caption alignment |
| `video_progress` | clip_index, message | Video generation |
| `caption_progress` | message | Caption rendering |
| `compose` | message | Final composition |
| `complete` | final_video_path, has_dialogue, has_captions | Done |
| `error` | message | Error occurred |

## Music Mode Pipeline

```
Manga panels + story beats
    ↓
┌──────────────────────────────────┐
│ 1. Gemini → lyrics + genre tags  │  (StoryboardPlanner)
└──────────────────────────────────┘
    ↓
┌──────────────────────────────────┬──────────────────────────────────┐
│ 2a. Veo 3.1 (4s clips × 4)     │ 2b. ElevenLabs → song (cloud)   │  (parallel)
└──────────────────────────────────┴──────────────────────────────────┘
    ↓
┌──────────────────────────────────┐
│ 3. FFmpeg concat → 16s base     │
│ 4. FFmpeg add music audio       │
└──────────────────────────────────┘
    ↓
┌──────────────────────────────────┐
│ 5. Panel-lock lyrics → captions │  (line i → panel i time window)
│ 6. Remotion → rolling lyrics    │  (RollingCaption, speaker="♪")
└──────────────────────────────────┘
    ↓
┌──────────────────────────────────┐
│ 7. verify_video() → complete    │
└──────────────────────────────────┘
```

### Music Mode Usage

```python
gen = AnimatedStoryGenerator()

async for event in gen.generate_animated_story_with_music_streaming(
    manga_result=manga_result,
    character_name="Mochi",
    story_summary="Mochi discovers a treasure map and goes on an adventure",
    enable_lyrics=True,
    clip_duration=4,
):
    if event.type == 'lyrics_progress':
        print(f"Lyrics: {event.data['message']}")
    elif event.type == 'music_progress':
        print(f"Music: {event.data['message']}")
    elif event.type == 'complete':
        print(f"Video: {event.data['final_video_path']}")
        print(f"Has music: {event.data['has_music']}")
```

### Lyrics & Music Best Practices

#### Panel-Aligned Lyrics

Gemini generates exactly 4 lines (one per panel) following the story arc:
- Line 1 → Panel 1 (setup) — gentle, building
- Line 2 → Panel 2 (action) — rising energy
- Line 3 → Panel 3 (twist) — energetic, catchy hook
- Line 4 → Panel 4 (payoff) — triumphant, uplifting

**Word budget**: 3-5 words per line. At singing speed, this fills ~4 seconds.

#### ElevenLabs Music Best Practices

Reference: [ElevenLabs Music Best Practices](https://elevenlabs.io/docs/overview/capabilities/music/best-practices)

**Prompting strategy** (from ElevenLabs docs):
- Intent-based prompts work best — "upbeat anime opening" outperforms overly detailed descriptions
- Both abstract mood descriptors ("playful", "energetic") and musical language ("piano arpeggios, bright synths") work
- Simple evocative keywords can yield creative results — don't over-specify

**Musical control parameters**:
- Include **BPM** for timing control (e.g., "130 BPM")
- Specify **key signatures** for mood (e.g., "C major" = bright, "A minor" = moody)
- The model accurately follows BPM and often captures intended key

**Vocal delivery descriptors**:
- Use expressive words: "breathy", "energetic", "raw", "playful", "gentle", "confident"
- These shape how the vocals sound — match to character persona
- For character-driven songs, the vocal style should reflect the character's personality

**Negative styles** (what to avoid):
- Always exclude "spoken word" for music tracks
- Exclude moods that clash: "slow, dark, heavy metal, sad" for upbeat anime content

**Composition plan structure** (per-section control):
```python
SongSection(
    section_name="Verse 1",              # Section label
    positive_local_styles=["gentle", "building", "soft opening"],  # Per-section mood
    negative_local_styles=[],             # Per-section exclusions
    duration_ms=4000,                     # Exact duration (3000-120000ms)
    lines=["Look a treasure map"],        # Lyrics (max 200 chars/line)
)
```

**Key API flags**:
- `respect_sections_durations=True` — enforces exact duration per section (critical for panel sync)
- `composition_plan` vs `prompt` — mutually exclusive; use composition_plan for panel control

#### Panel-Locked Captions

Each lyric line is displayed during its panel's time window (line 1 → 0-4s, line 2 → 4-8s, etc.) with 10% margin on each side. Words are evenly spaced for karaoke-style highlighting. This guarantees captions match their panel's visual story beat regardless of vocal timing.

**Note**: Forced alignment (Qwen3-ForcedAligner) is still used in dialogue mode where Qwen3-TTS guarantees the text is spoken.

#### Lyrics Format Example

```
[Verse 1]
Look a treasure map        ← Panel 1 (setup, gentle)
[Verse 2]
Off into the woods         ← Panel 2 (action, rising)
[Chorus]
We found the hidden gold   ← Panel 3 (twist, energetic)
Best adventure ever        ← Panel 4 (payoff, triumphant)
```

Gemini generates JSON with enriched style data:
```json
{
    "tags": "anime pop, bright female vocals, piano, acoustic guitar, 125 BPM, C major",
    "lyrics": "[Verse 1]\nLook a treasure map\n[Verse 2]\nOff into the woods\n[Chorus]\nWe found the hidden gold\nBest adventure ever",
    "vocal_style": "excited",
    "bpm": 125,
    "negative_tags": "slow, dark, heavy metal, sad, spoken word",
    "mood": "adventurous"
}
```

### Music Mode Events

| Event Type | Data | Description |
|------------|------|-------------|
| `lyrics_progress` | tags, lyrics | Gemini lyrics generation |
| `video_progress` | clip_index, message | Veo clip generation (parallel with music) |
| `music_progress` | audio_path, message | Music generation (parallel with video) |
| `caption_progress` | message | Rolling lyrics rendering |
| `complete` | has_music, has_lyrics, mood | Done |

### Known Issue: Colorspace

Remotion outputs `yuvj420p` (full range) while Veo outputs `yuv420p` (limited range).
The music pipeline normalizes to bt709 limited range after Remotion render via FFmpeg.

## Dependencies

- **qwen-tts**: Official Qwen3-TTS package (`pip install qwen-tts`) — torch mode
- **mlx_audio**: Mac local inference — local mode, also used for lyrics alignment
- **FAL_KEY**: FAL API access — cloud mode
- **Veo 3.1**: Via Google AI Studio (requires GOOGLE_API_KEY)
- **ElevenLabs**: Cloud music generation (`pip install elevenlabs>=2.34.0`)
- **Remotion**: Node.js (`cd remotion && npm install`)
- **FFmpeg**: For audio/video merging and colorspace normalization
- **transformers**: 4.57.6 (compatible with both qwen-tts and qwen-asr)

## Setup

```bash
# Python dependencies (torch mode)
pip install qwen-tts --no-deps
pip install torch torchaudio transformers==4.57.6 soundfile
pip install "elevenlabs>=2.34.0" "websockets>=13.0"

# Remotion setup (for karaoke captions)
cd remotion
npm install

# Environment variables (.env)
GOOGLE_API_KEY=your_google_key
FAL_KEY=your_fal_key  # Only needed for cloud TTS mode
ELEVENLABS_API_KEY=your_key  # Music generation (primary)
VEO_MODEL=veo-3.1-fast-generate-preview  # Fast for dev
```
