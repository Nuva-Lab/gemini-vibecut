# Gemini VibeCut

<img width="2528" height="1696" alt="image" src="https://github.com/user-attachments/assets/4ee2982c-d8fc-4a48-9d66-7e7e2ecd1200" />


> Turn your sleeping digital assets into personalized content.

**Human content at the core. Human directed. AI assisted.**

Built for the [Gemini 3 Hackathon](https://gemini3.devpost.com/).

---

## What It Does

Upload your photos and videos — VibeCut transforms them into a creative universe:

1. **Gallery** → Gemini analyzes your media (pets, people, scenes — photos and videos)
2. **Character** → Generate an anime character sheet from reference photos
3. **Manga** → Create a 4-panel story with your characters
4. **Video** → Animate the manga into a 16s video with music and lyrics

Each step produces a shareable artifact. You own every character, every story.

---

## How Gemini 3 Powers This

| Component | Model | Role |
|-----------|-------|------|
| Understanding | `gemini-3-flash-preview` | Gallery analysis, story planning, lyrics generation |
| Image Gen | `gemini-3-pro-image-preview` | Character sheets, manga panels |
| Video Gen | `veo-3.1-fast-generate-preview` | 4s animated clips from manga panels |
| Music | ElevenLabs | Background songs with vocals + lyrics |
| Captions | FFmpeg ASS | Karaoke-style rolling lyrics (white→gold) |

```
Photo + Video Gallery
    -> Gemini 3 Flash (understand — images inline, videos via Files API)
    -> Gemini 3 Pro Image (character + manga)
    -> Veo 3.1 (animate)
    -> ElevenLabs (music + vocals)
    -> FFmpeg ASS (karaoke captions)
    -> Final 16s video with music
```

---

## Quick Start

```bash
# Clone
git clone https://github.com/Nuva-Lab/gemini-vibecut.git
cd gemini-vibecut

# Python dependencies
pip install -r requirements.txt

# Environment
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY and ELEVENLABS_API_KEY

# Run
python ui/api_server.py
```

Open http://localhost:8000

---

## Project Structure

```
gemini-vibecut/
├── ui/
│   ├── api_server.py          # FastAPI backend (serves UI + API)
│   ├── demo.html              # Main UI (single-page app)
│   └── styles.css             # Styles
├── agent/                        # Client-side agent (browser JS)
│   ├── brain.js               # Client-side agent (Gemini function calling)
│   ├── context.js             # System prompt builder
│   ├── skills.js              # Gemini tool declarations
│   └── workspace.js           # IndexedDB storage (per-session)
├── skills/
│   ├── generate_character/    # Photo -> anime character sheet
│   ├── generate_manga/        # Characters + story -> 4-panel manga
│   ├── generate_video/        # Manga panel -> animated clip (Veo 3.1)
│   ├── generate_music/        # ElevenLabs music with lyrics
│   ├── generate_animated_story/ # Full pipeline orchestrator
│   ├── compose_final/         # FFmpeg video + audio composition
│   ├── render_captions/       # FFmpeg ASS karaoke captions
│   ├── align_captions/        # Word-level timestamp alignment
│   ├── understand_image/      # Gemini image analysis
│   └── verify_output.py       # ffprobe + Gemini Pro visual verification
├── remotion/                  # Remotion project (legacy, kept for complex motion graphics)
├── models/                    # Data models (Character, Project, World)
├── config.py                  # Configuration (env vars, model IDs)
├── assets/
│   ├── demo_photos/           # Sample photos + videos for demo
│   │   └── videos/            # 8 demo video clips (Mixkit CC0)
│   └── outputs/               # Generated content (gitignored)
└── tests/                     # Test suite
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Google AI Studio API key |
| `ELEVENLABS_API_KEY` | Yes | ElevenLabs API key (music generation) |
| `GEMINI_MODEL` | No | Override model (default: `gemini-3-flash-preview`) |
| `VEO_MODEL` | No | Override video model (default: `veo-3.1-fast-generate-preview`) |
| `FAL_KEY` | No | FAL API key (optional, for cloud TTS mode) |

See `.env.example` for all options.

---

## Architecture

```
┌─────────────────────────┐     ┌──────────────────────────────┐
│  Browser (demo.html)    │     │  FastAPI Server               │
│                         │     │  (api_server.py)              │
│  Agent Brain (JS)       │────>│                               │
│  - Gemini function call │     │  /api/upload-media            │
│  - Skill execution      │     │  /api/analyze-gallery         │
│  - IndexedDB workspace  │     │  /api/create-character        │
│                         │     │  /api/create-manga-stream     │
│                         │     │  /api/animate-story-stream    │
└─────────────────────────┘     └──────────┬───────────────────┘
                                           │
                              ┌────────────┼────────────┐
                              v            v            v
                         Google AI    ElevenLabs    FFmpeg
                      (Gemini, Veo)   (Music)    (Compose)
```

### Key Design Principles

1. **Agentic**: Gemini decides content dynamically — no hardcoded `if/else` for creative decisions
2. **Generative UX**: Each agent turn produces one rich UI widget (card + actions)
3. **Mixed media**: Gallery supports photos + videos; drag-and-drop upload; video understanding via Gemini Files API
4. **Per-session isolation**: Each browser tab gets its own IndexedDB and server-side output directory
5. **GPU-free**: Entire pipeline runs on cloud APIs + CPU (no GPU required)

---

## Video Pipeline

```
4 Manga Panels
    -> Veo 3.1 minimal motion (4s each, subtle animation)
    -> ElevenLabs music (with Gemini-generated lyrics)
    -> FFmpeg ASS karaoke captions (panel-locked, white→gold)
    -> FFmpeg compose + scale to 1080x1920
    -> 16s final video (1080x1920, h264+aac)
```

---

## Development

```bash
# Run server (auto-reload)
python ui/api_server.py

# Run tests
python tests/run_all_tests.py

# Test music pipeline
python tests/test_music_pipeline.py --full

# Test video pipeline
python tests/test_dialogue_pipeline.py --full
```

---

## License

MIT

---

## Acknowledgments

Built for the [Gemini 3 Hackathon](https://gemini3.devpost.com/) by Google DeepMind.

Powered by:
- [Gemini 3](https://ai.google.dev/gemini-api/docs) (understanding + image generation)
- [Veo 3.1](https://ai.google.dev/gemini-api/docs/video) (video generation)
- [ElevenLabs](https://elevenlabs.io/docs/overview/capabilities/music) (music generation)
- [FFmpeg](https://ffmpeg.org/) (composition, ASS karaoke captions)
