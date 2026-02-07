# Gemini VibeCut — UI Architecture

> This document describes the technical architecture of the demo UI.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GEMINI VIBECUT DEMO                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐  │
│  │   FastAPI Server  │    │    demo.html      │    │   Agent Brain     │  │
│  │   (api_server.py) │───▶│    (UI Layer)     │◀───│ (agent) │  │
│  │                   │    │                   │    │                   │  │
│  │ • Serves HTML     │    │ • Phone frames    │    │ • brain.js        │  │
│  │ • Static files    │    │ • Chat UI         │    │ • context.js      │  │
│  │ • /analyze API    │    │ • Cards/widgets   │    │ • skills.js       │  │
│  │ • /generate API   │    │ • Tech flow panel │    │                   │  │
│  └───────────────────┘    └───────────────────┘    └───────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. FastAPI Backend (`api_server.py`)

**Purpose:** Serves static files and provides API endpoints.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serves demo.html |
| `/health` | GET | Health check (returns model version) |
| `/api/analyze-gallery` | POST | Analyze photos with Gemini 3 Flash |
| `/api/create-character` | POST | Generate anime character with Nano Banana Pro |
| `/api/generate-story-options` | POST | Gemini generates personalized story options |
| `/api/create-comic` | POST | Generate multi-panel comic with Nano Banana Pro |
| `/api/create-scene` | POST | Generate single scene illustration |
| `/agent/` | GET | Serves agent ES modules |

**Model Usage by Endpoint:**
- `/api/analyze-gallery` → Gemini 3 Flash (`gemini-3-flash-preview`)
- `/api/generate-story-options` → Gemini 3 Flash (`gemini-3-flash-preview`)
- `/api/create-character`, `/api/create-comic`, `/api/create-scene` → Nano Banana Pro (`gemini-3-pro-image-preview`)

**Key Features:**
- Mounts `ui/` as static files
- Mounts `agent/` for ES module imports
- Uses Gemini 3 Flash Preview model

### 2. UI Layer (`demo.html`)

**Purpose:** Single-page application with phone frame mockups.

**Structure:**
```
demo.html
├── CSS Styles (inline)
├── HTML Structure
│   ├── Header (logo, mode badge)
│   ├── Phone Panel (Android frame)
│   │   ├── Photos View (gallery grid)
│   │   └── Create View (chat interface)
│   └── Activity Panel (tech flow log)
└── JavaScript
    ├── Session State Management
    ├── UI Renderers (cards, chat, etc.)
    └── Agent Integration (imports from /agent/)
```

**Views:**
| View | Content | Purpose |
|------|---------|---------|
| Photos | Gallery grid | Browse photos to transform |
| Create | Chat + cards | Agentic creative assistant |

### 3. Agent Brain (`agent/`)

**Purpose:** Client-side intelligence using Gemini 3's native function calling.

| File | Exports | Purpose |
|------|---------|---------|
| `brain.js` | `AgentBrain` class | Core loop: API calls, skill dispatch |
| `context.js` | `AgentContext`, `buildSystemPrompt` | State + dynamic prompts |
| `skills.js` | `skillFunctions` | Gemini function declarations |
| `index.js` | All exports | Convenience re-exports |

**Flow:**
```
User Action → AgentBrain.chat() → Gemini API → functionCall or text
                                      ↓
                           executeSkill() → UI Callback → Render Card
```

## Data Flow

### Photo Analysis Flow

```
1. User grants permission
2. demo.html collects photo URLs
3. POST /analyze with photos
4. Backend calls Gemini 3 with multi-modal input
5. Returns: characters, places, creative sparks
6. Agent Brain receives analysis result
7. Agent decides first action (via Gemini function calling)
8. UI renders cards progressively
```

### Agentic Interaction Flow

```
User Reaction (❤️, 😂, 😠, Next)
        ↓
agentContext.recordReaction()
        ↓
brain.chat('[User reacted ❤️ on char_0]')
        ↓
Gemini decides: highlight_subject | suggest_creation | text
        ↓
executeSkill() → handleSkillExecute() callback → Render UI
```

## Key Design Decisions

### ES Modules in Browser

We use native ES modules (`<script type="module">`) to separate concerns without a build step:

```html
<script type="module">
    import { AgentBrain } from '/agent/brain.js';
    import { AgentContext } from '/agent/context.js';
</script>
```

This requires the FastAPI server to mount `/agent/` directory.

### Session State

State is **in-memory only** (resets on page refresh):

```javascript
const sessionState = {
    analysisResult: null,    // Gemini analysis output
    photoUrls: [],           // For thumbnail lookup
    chatHistory: [],         // For UI restoration
    canvas: { characters: [], places: [], ideas: [] }
};
```

The `AgentContext` tracks:
- `shown` — Set of subject IDs already displayed
- `loved` — Set of subjects user ❤️'d
- `skipped` — Set of subjects user dismissed

### Native Function Calling

We don't build a custom decision loop. Gemini natively decides whether to:
- Output text (conversational response)
- Output `functionCall` (invoke a skill)

Skills are defined as Gemini function declarations in `skills.js`.

## ⚠️ CRITICAL: Agent Generates Content, Not Code

**This is the most important architectural principle.**

```javascript
// ❌ WRONG — Hardcoded conditionals for content
function getStoryOptions(character) {
    if (character.type === 'pet') {
        return ['Cozy day', 'Outdoor adventure'];  // Scripted!
    }
}

// ✅ RIGHT — Gemini generates content dynamically
async function getStoryOptions(character) {
    const response = await fetch('/api/generate-story-options', {
        body: JSON.stringify({
            character_name: character.name,
            character_traits: character.sourceAnalysis.what_you_notice,
            // Gemini reads context and decides
        })
    });
    return response.options;  // Whatever Gemini returns
}
```

**Why?**
- Hardcoded `if/else` = script pretending to be AI
- Gemini understands "pet", "comic", personality — let it decide
- Every user gets truly personalized options
- We're an AI assistant, not a template engine

**The rule:** If writing `if (type === 'pet')` for **content decisions**, move it to a Gemini call.

**Only acceptable static content:**
- Permission prompts ("Allow access to photos?")
- UI chrome (button labels, icons)
- Error messages

## Asset Handling — CRITICAL PATTERNS

> ⚠️ **Lesson Learned:** Path inconsistencies caused multiple bugs. Follow these patterns strictly.

### The Canonical Path Format

**Frontend uses absolute URL paths starting with `/assets/`:**

```javascript
// ✅ CORRECT: Absolute URL path
{ src: '/assets/demo_photos/pets/cat_01.webp' }

// ❌ WRONG: Relative paths (breaks when served from different routes)
{ src: '../assets/demo_photos/pets/cat_01.webp' }

// ❌ WRONG: Full URLs (breaks across environments)
{ src: 'http://localhost:8000/assets/demo_photos/pets/cat_01.webp' }
```

### Backend Path Resolution

**Every API endpoint that receives photo paths MUST handle multiple formats:**

```python
# In api_server.py - REQUIRED pattern for all endpoints
base_dir = Path(__file__).parent.parent  # project root

for photo_path in request.photos:
    if photo_path.startswith('../'):
        # Legacy format: ../assets/demo_photos/...
        resolved = base_dir / photo_path.replace('../', '')
    elif photo_path.startswith('/assets/'):
        # Canonical format: /assets/demo_photos/...
        resolved = base_dir / photo_path.lstrip('/')
    else:
        # Fallback: just filename
        resolved = base_dir / "assets" / "demo_photos" / photo_path
```

**Apply this pattern to:**
- `/api/analyze-gallery` ✅
- `/api/create-character` ✅
- Any future endpoint that handles image paths

### Asset Directory Structure

```
gemini-vibecut/
├── assets/                          # Mounted at /assets/
│   ├── demo_photos/                 # Static demo images
│   │   ├── pets/
│   │   ├── places/
│   │   └── people/
│   └── outputs/                     # Generated content
│       └── characters/              # Generated character sheets
├── ui/
│   └── api_server.py               # Mounts /assets/ directory
└── agent/                          # Mounted at /agent/
```

### Frontend → Backend Contract

| What | Frontend Sends | Backend Expects |
|------|----------------|-----------------|
| Demo photos | `/assets/demo_photos/pets/cat_01.webp` | Resolves to `gemini-vibecut/assets/demo_photos/pets/cat_01.webp` |
| Generated outputs | `/assets/outputs/characters/abc.png` | Resolves to `gemini-vibecut/assets/outputs/characters/abc.png` |
| User uploads (future) | `/uploads/{session_id}/photo_01.webp` | TBD - see Future section |

### Anti-Patterns to Avoid

| ❌ Don't | ✅ Do | Why |
|----------|-------|-----|
| Mix relative and absolute paths | Pick ONE format (absolute `/assets/`) | Inconsistency causes resolution bugs |
| Hardcode `localhost` URLs | Use path-only URLs | Breaks in production |
| Assume path format in backend | Always check multiple formats | Frontend might change |
| Store full filesystem paths in state | Store URL paths only | Portable across environments |
| Skip path validation | Log warnings for unresolved paths | Silent failures are debugging nightmares |

### Debugging Path Issues

When photos fail to load, check:

1. **Browser Network tab:** What path is being requested?
2. **Server logs:** Look for "Image not found" warnings
3. **Path resolution:** Add logging to see what path the backend tried

```python
# Helpful debugging in api_server.py
logger.info(f"Received path: {photo_path}")
logger.info(f"Resolved to: {resolved}")
logger.info(f"Exists: {resolved.exists()}")
```

---

## Future: User Uploads & Multi-Session (Cloudflare)

> Planning notes for production deployment with user-uploaded content.

### Requirements

1. **User uploads:** Photos from user's device, not just demo photos
2. **Multi-session:** User can return and continue previous sessions
3. **Cloudflare deployment:** Static frontend + Workers for API

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PRODUCTION ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │ Cloudflare Pages│    │ Cloudflare R2   │    │ Cloudflare      │        │
│  │ (Static UI)     │───▶│ (Image Storage) │◀───│ Workers (API)   │        │
│  │                 │    │                 │    │                 │        │
│  │ • demo.html     │    │ • User uploads  │    │ • /api/analyze  │        │
│  │ • agent/*.js    │    │ • Generated art │    │ • /api/generate │        │
│  │ • Static assets │    │ • Session data  │    │ • Auth/sessions │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### User Upload Path Format (Proposed)

```javascript
// Session-scoped uploads
`/uploads/${sessionId}/${filename}`

// Example
'/uploads/sess_abc123/photo_01.webp'
```

### Storage Strategy

| Content Type | Storage | URL Pattern | Lifecycle |
|--------------|---------|-------------|-----------|
| Demo photos | R2 (public bucket) | `/assets/demo_photos/...` | Permanent |
| User uploads | R2 (session bucket) | `/uploads/{session}/...` | 7 days TTL |
| Generated art | R2 (output bucket) | `/outputs/{session}/...` | 30 days TTL |
| Session state | KV or D1 | N/A (API only) | 30 days TTL |

### Migration Checklist

- [ ] Abstract path resolution into utility function (don't repeat in every endpoint)
- [ ] Add session ID to all user-uploaded paths
- [ ] Implement signed URLs for private uploads
- [ ] Add cleanup job for expired sessions
- [ ] Update frontend to handle upload flow (not just demo photos)
- [ ] Test path resolution works identically in local dev and Cloudflare

### Path Resolution Utility (Future)

```python
# Proposed: centralized path resolver
def resolve_asset_path(url_path: str, session_id: str = None) -> Path | R2Object:
    """
    Resolve a URL path to actual storage location.
    Works for both local dev (filesystem) and production (R2).
    """
    if url_path.startswith('/assets/'):
        return get_static_asset(url_path)
    elif url_path.startswith('/uploads/'):
        return get_session_upload(url_path, session_id)
    elif url_path.startswith('/outputs/'):
        return get_generated_output(url_path, session_id)
    else:
        raise ValueError(f"Unknown path format: {url_path}")
```

---

## My Creations — Persistent Asset Storage

> "My Creations" (internally: workspace) accumulates user's creative assets across sessions, preparing for future video generation.

### Why "My Creations"?

| Problem | Solution |
|---------|----------|
| Generated characters disappear on refresh | IndexedDB stores image blobs persistently |
| No visual library of creations | "My Creations" tab shows all accumulated assets |
| Can't reuse characters in video | Provides asset registry for future skills |
| "Workspace" is too technical | Consumer-friendly naming builds emotional connection |

### Storage Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WORKSPACE STORAGE (per-session)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────┐    ┌─────────────────────────┐               │
│  │     IndexedDB           │    │    localStorage         │               │
│  │ (creative-universe-ws)  │    │ (workspace_meta)        │               │
│  │                         │    │                         │               │
│  │ • images store          │    │ • characterCount        │               │
│  │   - id (string)         │    │ • characterIds[]        │               │
│  │   - blob (Blob)         │    │ • lastEvent             │               │
│  │   - originalUrl         │    │ • lastEventTime         │               │
│  │   - storedAt            │    │                         │               │
│  │                         │    │                         │               │
│  │ • characters store      │    │                         │               │
│  │   - id (string)         │    │                         │               │
│  │   - name                │    │                         │               │
│  │   - generatedImages[]   │    │                         │               │
│  │   - referencePhotos[]   │    │                         │               │
│  │   - sourceAnalysis      │    │                         │               │
│  │   - createdAt           │    │                         │               │
│  └─────────────────────────┘    └─────────────────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why IndexedDB + localStorage?

| Storage | Use Case | Why |
|---------|----------|-----|
| **IndexedDB** | Image blobs | Handles large binary data (MB per image), no size limit |
| **localStorage** | Quick metadata | Fast sync access for badges/counts, ~5MB limit OK for JSON |

### Workspace API (`workspace.js`)

```javascript
import { getWorkspace, hasWorkspaceContent } from '/agent/workspace.js';

const workspace = getWorkspace(SESSION_ID);  // Per-session instance
await workspace.init();                       // Opens IndexedDB

// Save a generated character
await workspace.saveCharacter(apiResponse, {
  referencePhotos: [...],          // Original photo URLs
  sourceAnalysis: {...}            // life_character from analysis
});

// List all characters
const characters = await workspace.getCharacters();

// Get image blob URL for display
const blobUrl = await workspace.getImageUrl('char_abc123_full_body');

// Delete a character (and its images)
await workspace.deleteCharacter('char_abc123');

// Quick check (uses localStorage, no async)
if (hasWorkspaceContent()) {
  updateWorkspaceBadge();
}
```

### Data Flow

```
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│ Character Gen  │───▶│ API Response   │───▶│  workspace.    │
│ (api_server)   │    │ {id, images}   │    │  saveCharacter │
└────────────────┘    └────────────────┘    └───────┬────────┘
                                                    │
                                                    ▼
                      ┌─────────────────────────────────────────┐
                      │         IndexedDB                        │
                      │ • Fetches image URLs as blobs           │
                      │ • Stores in 'images' object store       │
                      │ • Stores character metadata             │
                      │ • Updates localStorage for quick access │
                      └─────────────────────────────────────────┘
                                                    │
                                                    ▼
                      ┌────────────────┐    ┌────────────────┐
                      │ My Creations   │    │ Video Gen      │
                      │ (browse chars) │    │ (future)       │
                      └────────────────┘    └────────────────┘
```

### UI Components

| Component | Purpose |
|-----------|---------|
| **"Creations" Nav Tab** | Third nav button with badge showing character count |
| **My Creations View** | Grid of character cards with images |
| **Character Card** | Shows name, images, "Make Video" action (future) |
| **Empty State** | Friendly message when no creations exist yet |

### Future: Video Generation

"My Creations" is designed to be the asset registry for video generation:

```javascript
// Future API
const char = await workspace.getCharacter('char_abc123');

// Use character's images in video generation
const video = await generateVideo({
  character: char,
  scene: 'walking in a forest',
  style: char.style
});
```

---

## Running the Demo

```bash
python ui/api_server.py
# Open http://localhost:8000
```

## References

- [CLAUDE.md](../CLAUDE.md) — Developer guide
- [agent/CLAUDE.md](../agent/CLAUDE.md) — Agent brain architecture
