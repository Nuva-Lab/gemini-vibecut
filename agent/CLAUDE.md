# Agent Brain — Architecture

> Client-side agent using Gemini 3 native function calling.

---

## Architecture

```
User Action → brain.js → Gemini 3 API (with tools) → Function call OR text
                ↓
         executeSkill() → UI callback → Render result
```

### Files

| File | Purpose |
|------|---------|
| `brain.js` | Core loop: API calls, skill dispatch, conversation history |
| `context.js` | System prompt builder (rebuilt each turn with current state) |
| `skills.js` | Gemini function declarations |
| `workspace.js` | IndexedDB storage for characters |

---

## Key Principles

### 1. Native Function Calling
Gemini decides whether to call a tool or respond with text. No custom decision loop.

```javascript
// Gemini internally decides: text response OR function call
const response = await gemini.generate({ tools, contents });
```

### 2. Agentic = Gemini Decides Content
```javascript
// ❌ WRONG: Hardcoded
if (type === 'pet') return ['Cozy day', 'Adventure'];

// ✅ RIGHT: Gemini generates
const response = await gemini.generate({...});
```

### 3. Never Leave Users Stuck
All buttons → `agentChat()` → Agent responds with next steps

### 4. Multi vs Single Subject

| Phase | Handling |
|-------|----------|
| Gallery Analysis | MULTIPLE characters (cat, dog, person) |
| Character Creation | ONE subject across reference images |

---

## Debug API

### Session State
```bash
curl -s http://localhost:8000/api/debug/session/summary
curl -s http://localhost:8000/api/debug/session
```

### Server Logs
```bash
curl -s http://localhost:8000/api/debug/logs/errors
curl -s http://localhost:8000/api/debug/logs?lines=50
curl -s http://localhost:8000/api/debug/logs/list
```

### Session State Fields

| Field | Description |
|-------|-------------|
| `current_display` | Card currently shown |
| `chat_messages_ui` | Recent chat messages |
| `context.shown/loved/skipped` | Subject tracking |
| `pending_story` | Story being developed |
| `last_user_action` | Most recent action |

---

## Common Issues

### Module Won't Load
**Check:** `node -c agent/context.js`
**Cause:** Usually backticks inside template literals

### Button Click Does Nothing
**Check:** Debug session → `last_agent_response`
**Cause:** String mismatch (e.g., "Make a Manga" vs "Make a Comic")

### Wrong Photos Shown
**Check:** `image_indices` in analysis result
**Cause:** Media labels without filenames. Fixed by using `[Media X: filename]` labels.
**Note:** Videos are excluded from character/place cards (they get their own "Video Moments" card).

### show_card(creation_suggestion) Shows Nothing
**Check:** Logs show `show_card` with `card_type: creation_suggestion` but UI is blank
**Cause:** `brain.js` generic handler was dropping `subject_id` — only subject cards passed it through.
**Fix:** Generic handler now passes `{ card_type, subject_id, content, message }`.

### Agent Skips analyze_gallery
**Check:** Logs show `show_card` called before `analyze_gallery`
**Cause:** Saved characters confused Gemini into thinking analysis was done
**Fix:** Prompt clarifies: "Saved characters are NOT gallery subjects"

### Multi-Character ID Error
**Check:** Logs show `character_id: 'id1, id2'`
**Cause:** Gemini returns comma-separated IDs for multi-select
**Fix:** brain.js splits IDs and uses first: `character_id.split(',')[0].trim()`

---

## Skills Reference

| Skill | Purpose |
|-------|---------|
| `analyze_gallery` | Analyze mixed media gallery (photos + videos), detect characters/places |
| `show_card` | Display cards (subject, creation_suggestion, summary) |
| `create_character` | Generate anime character from reference photos |
| `ask_story_question` | Ask user a question with 2 options to build story |
| `confirm_story` | Show story outline for user approval |
| `create_manga` | Generate video keyframes (clean images, no manga artifacts) |
| `respond` | Send text message only |

## Character Model

```javascript
{
  name: "Mochi",           // User-provided
  pronouns: "she",         // he, she, they (default: they)
  persona: "A curious...", // One-line personality
  id: "abc123",            // UUID for reference
  generatedImages: [...]   // Character sheet
}
```

Agent prompts include pronouns: `"Mochi" (ID: abc, she/her)`

---

## Flow Examples

**Gallery exploration:**
```
grant_photos → analyze_gallery → show_card(char_0)
→ "Your orange tabby" with "Create Character" button
→ click → bottom sheet (name, pronouns, persona, photos)
→ generate → character saved to Assets
```

**Story building (interactive):**
```
"Make a manga for Mochi" → ask_story_question (mood)
→ user picks option → ask_story_question (setting)
→ user picks option → confirm_story (synopsis)
→ "Let's make it!" → create_manga (4 video keyframes)
```

**Story building (direct):**
```
"Mochi steals a cookie from the kitchen"
→ create_manga directly (specific concept given)
```
