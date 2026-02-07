# VibeCut Demo Interface

> Interactive demo UI for Gemini VibeCut.

## Overview

The demo interface (`demo.html`) is a single-page app served by FastAPI:

| Component | Description |
|-----------|-------------|
| **Phone Mockup** | Android/iPhone frame with photo gallery |
| **Photo Gallery** | Scrollable feed with demo photos |
| **Chat Interface** | Agentic creative assistant powered by Gemini 3 |
| **Capability Panel** | Live commentary showing which Gemini features are active |
| **Assets Tab** | Browse generated characters and videos |

## Quick Start

```bash
python ui/api_server.py
# Open http://localhost:8000
```

## Demo Flow

1. **Open demo** → Phone frame with photo gallery
2. **Tap "Create"** → Chat interface with welcome message
3. **Grant photo access** → Gemini analyzes gallery (pets, people, scenes)
4. **Browse results** → Cards for each detected subject
5. **Create character** → Name, pronouns, persona → anime character sheet
6. **Make manga** → Choose story → 4-panel manga
7. **Animate** → 16s video with music and lyrics

## Files

| File | Purpose |
|------|---------|
| `demo.html` | Main UI (single-page app) |
| `api_server.py` | FastAPI backend |
| `styles.css` | Stylesheet |
| `DEMO.md` | This file |

## Demo Photos (30 total)

| Category | Content | Count |
|----------|---------|-------|
| Pets | Orange tabby cat + golden retriever | 10 |
| Family | Candid beach moments | 10 |
| Worlds | Tokyo neon streets | 10 |

Located in `assets/demo_photos/`.
