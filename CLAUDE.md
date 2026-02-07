# Gemini VibeCut — Developer Guide

> Turn your sleeping digital assets into personalized content.

**Core thesis:** Human content at the core. Human directed. AI assisted.

---

## Technical Stack

| Layer | Model | Use |
|-------|-------|-----|
| Understanding | `gemini-3-flash-preview` | Gallery analysis, planning, lyrics generation |
| Image Gen | `gemini-3-pro-image-preview` | Character sheets, manga panels |
| Video Gen | `veo-3.1-fast-generate-preview` | 4s minimal motion clips |
| Music Gen | `ElevenLabs Music` (cloud) | Background songs with vocals + lyrics |
| TTS | `Qwen3-TTS` (local) | Character dialogue voices |
| Alignment | `Qwen3-ForcedAligner` (local) | Word-level timestamps for captions |

### GPU Requirements: NONE for critical path

The entire pipeline runs on **cloud APIs + CPU**. No GPU needed.

| Component | Compute | Deployment |
|-----------|---------|------------|
| Gemini (understanding, lyrics, images) | Cloud API | API key only |
| Veo 3.1 (video clips) | Cloud API | API key only |
| ElevenLabs (music + vocals) | Cloud API | API key only |
| FFmpeg (merge, normalize) | CPU | Install binary |
| Remotion (captions) | Node.js/CPU | `npm install` |
| Qwen3-TTS (dialogue mode) | Cloud via FAL **or** local MPS/CUDA | FAL_KEY for cloud |

---

## Quick Start

```bash
pkill -f "python.*api_server" 2>/dev/null
sleep 1
python ui/api_server.py &
sleep 2
curl -s http://localhost:8000/health
```

**Expected:** `{"status":"healthy","model":"gemini-3-flash-preview"}`
**Demo:** http://localhost:8000/

---

## Debug APIs

Debug endpoints for inspecting live app state.

### Browser Session State
```bash
# Quick snapshot
curl -s http://localhost:8000/api/debug/session/summary

# Full state (context, chat, characters)
curl -s http://localhost:8000/api/debug/session | python -m json.tool | head -50

# Per-session (multi-user)
curl -s "http://localhost:8000/api/debug/session/summary?session_id=..."
```

### Server Logs
```bash
curl -s http://localhost:8000/api/debug/logs/errors
curl -s http://localhost:8000/api/debug/logs?lines=50
```

### Available Endpoints
| Endpoint | Purpose |
|----------|---------|
| `GET /api/debug/session` | Full session state (context, history, characters) |
| `GET /api/debug/session/summary` | Quick snapshot of current state |
| `GET /api/debug/logs?lines=N` | Recent N lines of server logs |
| `GET /api/debug/logs/errors` | ERROR and WARNING lines only |
| `GET /api/debug/logs/list` | List available log files |
| `POST /api/debug/session` | Browser posts state updates (automatic) |

---

## Key Principles

### 1. Storyboard Mindset
Images are **video keyframes**, not static illustrations:
- Cinematic camera angles (close-up, wide shot, low angle, etc.)
- Action-driven plots: setup → action → twist → payoff
- "Show, don't tell" — no narration, only character dialogue
- Characters CAN and SHOULD speak (even pets!)

### 2. Character = Name + Pronouns + Persona + Reference Sheet
```
Character {
  name: "Mochi"                    // User-provided
  pronouns: "she"                  // he, she, they (default: they)
  persona: "A curious adventurer"  // One-line personality
  generatedImages: [...]           // Reference sheet
}
```

### 3. Agentic = Gemini Decides Content
```javascript
// ❌ WRONG: Hardcoded conditionals
if (character.type === 'pet') return ['Cozy day', 'Adventure'];

// ✅ RIGHT: Gemini generates dynamically
const response = await gemini.generate({...});
return response.options;
```

### 4. Never Leave Users Stuck
All button clicks → `agentChat()` → Agent responds with next steps

### 5. Generative UX — One Rich Widget Per Turn
Each agent turn = ONE rich widget that combines message + actions.

### 6. Gemini API Conventions

| Parameter | Value | Reason |
|-----------|-------|--------|
| `temperature` | `1.0` | Always 1.0, never change |
| `thinking_level` | `"low"` | Fast responses for agent chat |
| API | AI Studio | Never use Vertex AI |

```python
response = client.models.generate_content(
    model=GEMINI_MODEL,
    contents=contents,
    config=types.GenerateContentConfig(
        temperature=1.0,
        thinking_config=types.ThinkingConfig(thinking_level="low"),
    )
)
```

### 7. Per-Session Isolation
Each browser tab gets its own:
- `sessionStorage`-backed session ID (survives refresh, isolated per tab)
- IndexedDB database (`vibecut-ws-{sessionId}`)
- Server-side output directory (`assets/outputs/sessions/{sessionId}/`)
- Debug state (keyed by session ID)

---

## Video Pipeline (Veo 3.1 Minimal Motion)

Docs: https://ai.google.dev/gemini-api/docs/video

```
4 Manga Panels
    → Veo 3.1 minimal motion (4s each, NO audio)
    → 4 video clips with subtle animation
    → FFmpeg concatenate
    → 16s Silent Video Base
    → [Then: music/TTS + Remotion captions added on top]
```

**Duration Constraints (Veo 3.1):**

| Mode | Duration Options | Notes |
|------|-----------------|-------|
| Pure image-to-video (no last_frame) | 4s, 6s, 8s | Most flexible |
| With last_frame | 8s only | Required for interpolation |
| With reference_images | 8s only | Required for multi-ref |

```python
from google.genai import types

for panel in panels:
    image = types.Image.from_file(location=str(panel))
    operation = client.models.generate_videos(
        model="veo-3.1-generate-preview",
        prompt="""Animate with very subtle, minimal motion only.
ONLY add:
- Gentle breathing (slight chest movement)
- 1-2 soft eye blinks
- Tiny hair/fur sway
DO NOT move characters or change poses.
AUDIO: Soft ambient sounds. NO speech, NO music.""",
        image=image,
        config=types.GenerateVideosConfig(
            aspect_ratio="9:16",
            duration_seconds=4,
        ),
    )
```

---

## Full Pipeline Architecture

### End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. UNDERSTAND — Gemini 3 Flash              skills/understand_image/   │
│     User uploads photos → gallery analysis                              │
│     Detects: pets, people, scenes, moods, creative sparks               │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. CHARACTER — Gemini 3 Pro Image           skills/generate_character/ │
│     Reference photos + analysis → anime character sheet                 │
│     Output: full_body + portrait (9:16 vertical)                        │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. MANGA — Gemini 3 Pro Image               skills/generate_manga/    │
│     Characters + story beats → 4-panel manga                            │
│     Each panel: image + dialogue + camera direction                     │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼  (two modes)
   ┌─────┴──────┐
   ▼            ▼
 MUSIC       DIALOGUE
 (primary)   (optional)
```

### Music Video Mode (Primary — no Qwen3 needed)

```
4 Manga Panels
    │
    ├──→ Gemini Flash: generate lyrics + style tags    (storyboard_planner.py)
    │       1 lyric line per panel, story arc: setup→action→twist→payoff
    │
    ├──→ ElevenLabs: music + vocals from lyrics        (elevenlabs_music.py)
    │       composition_plan API, per-section duration control
    │
    ├──→ Veo 3.1 Fast: 4s minimal motion clips         (generate_video/)
    │       4 clips × 4s = 16s silent video (runs parallel with music)
    │
    ├──→ FFmpeg: merge video + music                   (compose_final/)
    │
    ├──→ Remotion: panel-locked rolling lyrics          (render_captions/)
    │       Direct panel↔lyric mapping (no forced alignment needed)
    │
    └──→ FINAL: 16s MP4, 1080x1920, h264+aac
```

### Dialogue Mode (Optional — uses Qwen3-TTS)

```
4 Manga Panels + Character Personas
    │
    ├──→ Qwen3-TTS: character voice per panel          (qwen_tts/)
    │       Torch: VoiceDesign→Clone (consistent voices)
    │       Local: mlx VoiceDesign / Cloud: FAL API
    │
    ├──→ Qwen3-ForcedAligner: word timestamps           (align_captions/)
    │       ~30ms precision per word
    │
    ├──→ Veo 3.1 Fast: clips matched to TTS duration   (generate_video/)
    │
    ├──→ FFmpeg: merge per-clip audio + video           (compose_final/)
    │
    ├──→ Remotion: karaoke captions (word-by-word)      (render_captions/)
    │
    └──→ FINAL: 16s MP4, 1080x1920, h264+aac
```

### Component Status

| Component | Skill | Status |
|-----------|-------|--------|
| Gallery analysis | `understand_image/` | ✅ |
| Character sheets | `generate_character/` | ✅ |
| Manga panels | `generate_manga/` | ✅ |
| Video clips | `generate_video/` | ✅ |
| Music + vocals | `generate_music/elevenlabs_music.py` | ✅ |
| Lyrics gen | `storyboard_planner.py` | ✅ |
| TTS (dialogue) | `qwen_tts/` | ✅ |
| Word alignment | `align_captions/` | ✅ |
| Captions | `render_captions/` | ✅ |
| Compose | `compose_final/` | ✅ |
| Verification | `verify_output.py` | ✅ |
| Orchestrator | `generate_animated_story/` | ✅ |

---

## Testing

```bash
# Dialogue pipeline (Torch TTS + Veo + Captions)
python tests/test_dialogue_pipeline.py --full

# Music pipeline (ElevenLabs + Veo + lyrics)
python tests/test_music_pipeline.py --full
python tests/test_music_pipeline.py --music-only
python tests/test_music_pipeline.py --lyrics-only
```

### Key Files
| File | Purpose |
|------|---------|
| `tests/test_dialogue_pipeline.py` | CLI test (`--full` for torch TTS) |
| `tests/test_music_pipeline.py` | CLI test (`--music-only`, `--lyrics-only`, `--full`) |
| `skills/generate_animated_story/` | Full pipeline orchestrator |
| `skills/generate_music/elevenlabs_music.py` | ElevenLabs Music API client |
| `skills/generate_animated_story/storyboard_planner.py` | Lyrics generation (Gemini) |
| `skills/verify_output.py` | Output verification (ffprobe) |
| `skills/compose_final/` | FFmpeg concat with auto-normalization |
| `skills/align_captions/` | Word timestamps (dialogue mode) |
| `skills/render_captions/` | Remotion wrapper (karaoke + rolling lyrics) |

---

## Known Issues & Fixes

### 1. JavaScript Template Literal Syntax Error
**Symptom:** Module won't load, `AgentBrain` is null
**Fix:** No backticks inside template literals

### 2. Gallery Analysis Wrong Photo Indices
**Fix:** Add `[Photo X]` labels before each image in API request

### 3. Manga Panels Mixed B&W and Color
**Fix:** Explicit "FULL COLOR" in style prompts

### 4. Veo Duration Constraints
`last_frame` and `reference_images` modes require 8s duration. Pure image-to-video allows 4/6/8s.

### 5. Corrupt Concat from Mixed Resolutions
**Root cause:** Veo outputs 720x1280, Remotion outputs 1080x1920. Stream copy can't handle mixed resolutions.
**Fix:** `concatenate_scenes()` probes all clips with ffprobe, auto-normalizes to 1080x1920 when resolutions differ.

### 6. Zero-Duration Words from Aligner
**Root cause:** Qwen3-ForcedAligner sometimes produces `startMs == endMs`.
**Fix:** `_sanitize_word_segments()` ensures min 50ms per word.

### 7. Remotion Colorspace Mismatch
**Root cause:** Veo outputs `yuv420p` (limited range), Remotion outputs `yuvj420p` (full range).
**Fix:** Normalize after Remotion: `-pix_fmt yuv420p -color_range tv -colorspace bt709 -color_trc bt709 -color_primaries bt709`.

### 8. Remotion Frame Range Off-by-One
**Root cause:** 16s × 30fps = 480 frames, but Remotion range is 0-479.
**Fix:** `duration_frames - 1` in `render_captions.py`.

---

## Roadmap

### Done
- [x] Gallery analysis (Gemini 3 Flash, multi-image)
- [x] Character sheet generation (Gemini 3 Pro Image)
- [x] 4-panel manga generation with story beats
- [x] Veo 3.1 minimal motion video (4s clips)
- [x] ElevenLabs music generation with lyrics
- [x] Remotion karaoke caption overlay
- [x] Full pipeline orchestrator (dialogue + music modes)
- [x] Per-session isolation (multi-user support)
- [x] Open source cleanup

### Next
- [ ] User photo upload (currently demo photos only)
- [ ] Video understanding and processing
- [ ] End-to-end web UI flow
- [ ] Production deployment (Cloudflare Pages + API server)
- [ ] Demo video recording

---

## Reference Links

- [Gemini 3 Hackathon](https://gemini3.devpost.com/)
- [Gemini API Docs](https://ai.google.dev/gemini-api/docs)
- [Veo Video Generation](https://ai.google.dev/gemini-api/docs/video)
- [ElevenLabs Music Best Practices](https://elevenlabs.io/docs/overview/capabilities/music/best-practices)
- [Agent Architecture](./agent/CLAUDE.md)
