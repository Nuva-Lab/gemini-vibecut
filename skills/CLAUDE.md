# Skills Catalog

> Skills are focused, composable capabilities that the Creative Agent orchestrates.

## Skill Architecture

Following [Anthropic's Agent Skills Pattern](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills):

```
skills/
├── CLAUDE.md                         # This file - skill catalog
├── understand_image/
│   ├── SKILL.md                      # Metadata + contract (YAML frontmatter)
│   └── understand_image.py           # Implementation
├── generate_character/
│   ├── SKILL.md
│   └── generate_character.py
├── generate_manga/
│   ├── SKILL.md
│   └── generate_manga.py
├── generate_tts/
│   ├── SKILL.md
│   └── generate_tts.py
├── generate_video/
│   ├── SKILL.md
│   └── generate_video.py
├── generate_animated_story/          # Orchestrator: full pipeline
│   ├── SKILL.md
│   └── generate_animated_story.py
├── generate_music/
│   ├── SKILL.md
│   ├── generate_music.py
│   └── elevenlabs_music.py          # Cloud music gen, per-section control
├── compose_final/
│   ├── SKILL.md
│   └── compose_final.py
├── qwen_tts/                         # Dual-mode: local (mlx) / cloud (FAL)
│   ├── SKILL.md
│   └── qwen_tts.py
├── align_captions/                   # Dual-mode: local (mlx) / cloud (qwen_asr)
│   ├── SKILL.md
│   └── align_captions.py
└── render_captions/                  # Remotion karaoke captions
    ├── SKILL.md
    └── render_captions.py
```

## Skill File Format

Each `SKILL.md` starts with **YAML frontmatter** that is pre-loaded into context:

```yaml
---
name: Skill Name
description: One-line description loaded at agent startup
triggers:
  - When to activate this skill
  - Keywords that suggest this skill
---
```

The body contains detailed instructions loaded only when the skill is triggered (progressive disclosure).

---

## Available Skills

| Skill | Directory | Description | Model |
|-------|-----------|-------------|-------|
| **Image Understanding** | `understand_image/` | Analyze photos (pet/person) | Gemini 3 |
| **Character Generation** | `generate_character/` | Create anime characters with style transfer | Nano Banana Pro |
| **Manga Generation** | `generate_manga/` | Multi-panel manga with streaming | Nano Banana Pro |
| **TTS Generation** | `generate_tts/` | Multi-speaker dialogue (Gemini voices) | Gemini TTS Pro |
| **Qwen3-TTS** | `qwen_tts/` | Dual-mode TTS with persona support | mlx / FAL |
| **Caption Alignment** | `align_captions/` | Word-level timestamps (~30ms) | mlx / qwen_asr |
| **Caption Rendering** | `render_captions/` | Karaoke caption overlay | Remotion |
| **Video Generation** | `generate_video/` | Animate panels into video clips | Veo 3.1 |
| **Animated Story** | `generate_animated_story/` | Full pipeline: TTS → Align → Video → Captions | All |
| **Music Generation** | `generate_music/` | Create background music (optional) | Music API |
| **ElevenLabs Music** | `generate_music/elevenlabs_music.py` | Cloud song gen with composition_plan: per-section duration, lyrics, local/global styles, BPM, vocal delivery (primary) | ElevenLabs |
| **Final Composition** | `compose_final/` | Assemble video + audio with per-clip sync | FFmpeg |
| **Verification** | `verify_output.py` | ffprobe-based output validation (duration, resolution, streams) | ffprobe |

---

## Progressive Disclosure Levels

Following [Anthropic's Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents):

| Level | What's Loaded | When |
|-------|---------------|------|
| **Level 1** | `name` + `description` from YAML frontmatter | Agent startup |
| **Level 2** | Full `SKILL.md` body | When skill is triggered |
| **Level 3** | Referenced files, examples | On-demand |

This keeps context tight while allowing deep detail when needed.

---

## Skill Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER ASSETS                                    │
│                    (pet photo, selfie, world photo)                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        understand_image                                  │
│                     (Gemini 3 multimodal)                               │
│                                                                         │
│  pet_photo ──→ pet_analysis                                             │
│  selfie ─────→ person_analysis                                          │
│  scene ──────→ world_analysis                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       generate_character                                 │
│                       (Nano Banana Pro)                                 │
│                                                                         │
│  pet_analysis ────→ Character(name="Mochi", images={...})              │
│  person_analysis ─→ Character(name="Hero", images={...})               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        generate_manga                                    │
│                       (Nano Banana Pro)                                 │
│                                                                         │
│  characters + story ──→ panels[] + dialogues[]                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌───────────────────────────────┐  ┌───────────────────────────────────────┐
│   MODE A: generate_tts       │  │   MODE B: ElevenLabs + lyrics gen     │
│       (Qwen3-TTS)            │  │       (ElevenLabs cloud)              │
│                               │  │                                       │
│  dialogues ──→ speech_audio[] │  │  story + panels ──→ lyrics + song    │
│           ──→ durations[]     │  │  (Gemini lyrics gen + ElevenLabs)    │
└───────────────────────────────┘  └───────────────────────────────────────┘
                    │                               │
                    ▼                               │
┌─────────────────────────────────────────────────────────────────────────┐
│                        generate_video                                    │
│                          (Veo 3.1)                                      │
│                                                                         │
│  panels[] + durations[] ──→ video_clips[] (panel as keyframe)          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        compose_final                                     │
│                          (FFmpeg)                                       │
│                                                                         │
│  video_clips + speech_audio + bgm ──→ final_output.mp4                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### Audio-Video Sync (CRITICAL)

**Never concatenate audio and video separately!** Use per-clip sync:

```
For each panel:
1. TTS → audio_path, duration
2. Video → video_path (silent - Veo has no audio)
3. Pad audio if shorter than video
4. Overlay audio → synced_clip
5. Collect synced_clips[]

Then: concatenate(synced_clips[]) → final (perfectly synced)
```

See `compose_final/SKILL.md` for FFmpeg patterns.

### Output Verification (CRITICAL)

**Never trust pipeline output without verification.** The pipeline uses `verify_video()` after every final concat to check:
- Duration matches expected (within 2s tolerance)
- Resolution is 1080x1920 (not Veo's raw 720x1280)
- Audio stream present (when dialogue was generated)

If resolution mismatches are detected, `concatenate_scenes()` auto-normalizes all clips to 1080x1920 before concat. The `complete` event includes `verified: true/false` and `verification_failures` for the UI.

```python
from skills.verify_output import verify_video

result = verify_video(
    path=final_path,
    expected_duration=16.0,
    expected_width=1080,
    expected_height=1920,
    require_audio=True,
)
# result.passed, result.failures, result.actual_duration, etc.
```

---

## Usage Example

```python
from skills import (
    ImageUnderstanding,
    CharacterGenerator,
    MangaGenerator,
    TTSGenerator,
    VideoGenerator,
    MusicGenerator,
    VideoComposer,
)

# 1. Understand assets
understand = ImageUnderstanding()
pet_analysis = await understand.execute(pet_photo, "pet")

# 2. Create characters
char_gen = CharacterGenerator()
character = await char_gen.execute(pet_analysis, name="Mochi")

# 3. Generate manga panels with dialogue
manga_gen = MangaGenerator()
manga = await manga_gen.generate_manga(
    character_refs=[{"name": "Mochi", "path": character.image_path}],
    story_beats=["Mochi discovers a treasure map", "Mochi sets off on adventure"],
    dialogues=["Mochi: What's this?", "Mochi: Adventure awaits!"],
)

# 4. Generate TTS for dialogue (TTS-first for duration sync)
tts = TTSGenerator()
tts.set_voice_mapping({"Mochi": "Fenrir"})  # Excitable voice for pet

audio_results = []
for panel in manga.panels:
    audio_path, duration = await tts.generate_panel_audio(
        panel_dialogue=panel.dialogue,
        characters=[{"name": "Mochi"}],
    )
    audio_results.append((audio_path, duration))

# 5. Generate video clips (duration matches TTS)
video_gen = VideoGenerator()
video_clips = []
for panel, (audio_path, duration) in zip(manga.panels, audio_results):
    clip = await video_gen.generate_clip(
        keyframe=panel.image_path,
        duration=duration,  # Match TTS duration
    )
    video_clips.append(clip)

# 6. Generate background music
music_gen = MusicGenerator()
total_duration = sum(d for _, d in audio_results)
bgm_path = await music_gen.execute(mood="adventurous", duration=total_duration)

# 7. Compose final
composer = VideoComposer()
final_path = await composer.execute(
    video_clips=video_clips,
    speech_audio=[a for a, _ in audio_results],
    bgm=bgm_path,
)
```

---

## Adding New Skills

1. Create skill directory: `skills/skill_name/`
2. Create `SKILL.md` with YAML frontmatter
3. Create `skill_name.py` with implementation
4. Add to `skills/__init__.py`
5. Document in this catalog

## ElevenLabs Music — Quick Reference

Best practices from [ElevenLabs Music Docs](https://elevenlabs.io/docs/overview/capabilities/music/best-practices):

| Technique | Example | Effect |
|-----------|---------|--------|
| Intent-based prompt | "upbeat anime opening" | Better than verbose descriptions |
| BPM control | "130 BPM" in tags | Precise timing |
| Key signature | "C major" / "A minor" | Mood control (bright vs moody) |
| Vocal delivery | "breathy", "energetic", "playful" | Shapes vocal tone |
| Negative styles | "slow, dark, spoken word" | Avoids unwanted directions |
| Section names | "Verse 1", "Chorus" | Controls song structure |
| `respect_sections_durations=True` | — | Enforces exact per-section timing |

**API constraints**: `composition_plan` and `prompt` are mutually exclusive. Duration per section: 3000-120000ms. Max 200 chars per lyrics line. Output: MP3 44.1kHz 128-192kbps.

## References

- [Anthropic: Equipping Agents with Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Anthropic: Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [ElevenLabs Music Best Practices](https://elevenlabs.io/docs/overview/capabilities/music/best-practices)
- [ElevenLabs Music API](https://elevenlabs.io/docs/overview/capabilities/music)
