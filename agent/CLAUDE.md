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
| Story Building | ONE or MULTIPLE characters (comma-separated IDs) |
| Manga Generation | ONE or MULTIPLE characters (array) |

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

### Multi-Character Stories
**Flow:** Gemini sends comma-separated IDs: `character_id: 'id1, id2'`
**Handling:** `brain.js` resolves ALL IDs into a `characters` array. Story cards accept both single character and array. `renderStoryQuestionCard` and `renderStoryConfirmCard` show pills for all characters.
**Re-trigger:** When user selects/deselects characters in Assets tab during active story flow (`storyFlowActive`), `selectCharacterForCreate` sends updated selection to `agentChat`, restarting story building.

### Stale Card Buttons
**Pattern:** `deactivatePreviousCards(device)` called at the top of every card renderer.
**Behavior:** Disables all buttons/inputs in prior chat cards, dims stale containers to `opacity: 0.6`.
**Scope:** All card types: permission, character, place, video, idea, creation_suggestion, story question, story confirm, manga.

### Uploaded Subject Priority
**Analysis:** `LifeCharacter` and `MeaningfulPlace` have `has_uploaded_media: bool` flag (computed from overlap between `image_indices` and uploaded media indices).
**Card ordering:** `getNextUnshownSubject()` gives priority 0 to uploaded subjects (above pets=1, people=2).
**Character creation:** Threshold lowered to 1+ photos for uploaded subjects (from 3).

### Manga Character Consistency
**Problem:** Image model can hallucinate different characters on complex story beats when relying only on visual reference.
**Fix:** Before panel generation, `_describe_character()` calls Gemini Pro to analyze the character sheet and produce a text description (hair, clothing, accessories). This is embedded in every panel prompt as `APPEARANCE:` alongside the visual reference — dual anchor approach.

---

## Skills Reference

| Skill | Purpose |
|-------|---------|
| `analyze_gallery` | Analyze mixed media gallery (photos + videos), detect characters/places |
| `show_card` | Display cards (subject, creation_suggestion, summary) |
| `create_character` | Generate anime character from reference photos |
| `ask_story_question` | Ask user a question with 2 options to build story (supports multi-character via comma-separated IDs) |
| `confirm_story` | Show story outline for user approval (supports multi-character) |
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

**Multi-character story:**
```
User selects Mochi in Assets → starts story → selects Goldie in Assets
→ storyFlowActive detected → agentChat re-triggers with both characters
→ ask_story_question(character_id: "id1, id2") → pills for both shown
→ confirm_story → create_manga with characters array
```
