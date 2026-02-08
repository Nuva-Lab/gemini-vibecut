"""
API Server for Creative Universe Gallery Analysis.

This FastAPI server provides:
1. Static file serving for the demo UI
2. /api/analyze-gallery endpoint for batch image analysis with Gemini 3

Run with: uvicorn api_server:app --reload --port 8000
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from google import genai
from google.genai import types

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import GOOGLE_API_KEY, GEMINI_MODEL, NANO_BANANA_MODEL
from models.character import Character
from skills.generate_character.generate_character import CharacterGenerator
from skills.generate_manga.generate_manga import MangaGenerator, MangaPanel, StreamEvent
from skills.generate_animated_story.generate_animated_story import AnimatedStoryGenerator

# =============================================================================
# Setup Logging — File + Console for Claude Code debugging
# =============================================================================

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Generate session log filename with timestamp
_session_start = time.strftime("%Y%m%d_%H%M%S")
_log_file = LOGS_DIR / f"server_{_session_start}.log"

# Configure logging to both file and console
# Use force=True to override any existing handlers (uvicorn issue)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(_log_file, mode='a'),
        logging.StreamHandler()
    ],
    force=True
)
logger = logging.getLogger("api_server")
logger.setLevel(logging.INFO)
logger.info(f"Server session started. Log file: {_log_file}")

# Also log to file directly for critical errors
def log_error(msg: str):
    """Log error to both logger and directly to file (in case logger fails)."""
    logger.error(msg)
    with open(_log_file, 'a') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - ERROR - {msg}\n")
        f.flush()

# Initialize FastAPI app
app = FastAPI(
    title="Creative Universe API",
    description="Gallery analysis powered by Gemini 3",
    version="0.1.0",
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini client
client = genai.Client(api_key=GOOGLE_API_KEY)

# =============================================================================
# Debug Session State Storage (for Claude Code introspection)
# =============================================================================
# This allows Claude Code to inspect the running browser session state

_debug_sessions: dict[str, dict] = {}  # keyed by session_id


def _get_debug_session(session_id: str) -> dict:
    """Get or create debug state for a session."""
    if session_id not in _debug_sessions:
        _debug_sessions[session_id] = {
            "session_id": session_id,
            "last_updated": None,
            "context": {},
            "conversation_history": [],
            "pending_story": None,
            "saved_characters": [],
            "generated_characters": [],
            "analysis_result": None,
            "last_user_action": None,
            "last_agent_response": None,
        }
    return _debug_sessions[session_id]


# =============================================================================
# Session-Scoped Output Directories
# =============================================================================


def get_session_output_dir(session_id: Optional[str] = None) -> Path:
    """Get output directory, optionally scoped to a session."""
    base = Path(__file__).parent.parent / "assets" / "outputs"
    if session_id:
        session_dir = base / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir
    return base


# =============================================================================
# Request/Response Models
# =============================================================================

class MediaItem(BaseModel):
    """A single media item (photo or video) in the gallery."""
    path: str
    type: str = "image"  # "image" or "video"
    uploaded: bool = False  # True if user-uploaded (not demo media)


class GalleryAnalysisRequest(BaseModel):
    """Request to analyze gallery media (photos and videos)."""
    photos: list[str] = []  # Legacy: image paths only
    media: list[MediaItem] = []  # New: mixed media with type info
    base_path: Optional[str] = None


class LifeCharacter(BaseModel):
    """A recurring character in the user's life story (pet, person, subject)."""
    name_suggestion: str
    who_they_are: str
    appearances: int
    what_you_notice: str
    type: str  # pet, person, recurring_subject
    image_indices: list[int] = []  # Which photo indices this character appears in
    has_uploaded_media: bool = False  # True if any index overlaps with user uploads


class MeaningfulPlace(BaseModel):
    """A place that matters in the user's gallery."""
    place_description: str
    why_it_seems_to_matter: str
    mood: str
    appearances: int
    image_indices: list[int] = []  # Which photo indices show this place
    has_uploaded_media: bool = False  # True if any index overlaps with user uploads


class EmotionalMoment(BaseModel):
    """A specific photo that captures an emotional moment."""
    photo_index: int
    what_you_see: str


class CreativeSpark(BaseModel):
    """A personalized creative suggestion based on the gallery."""
    idea: str
    why_this_fits: str
    based_on: str


class ImageDetail(BaseModel):
    """Details about a single image in context of the gallery."""
    index: int
    primary_subject: str
    emotional_read: str
    connections: str


class GalleryAnalysisResponse(BaseModel):
    """
    Deep, personal gallery analysis result.

    This isn't just categorization—it's seeing the story in someone's photos.
    """
    # The warm opening that shows we really looked
    opening_reaction: str

    # The characters in their life story
    life_characters: list[LifeCharacter] = []

    # Places that matter to them
    meaningful_places: list[MeaningfulPlace] = []

    # The overall story of this gallery
    gallery_story: str

    # Patterns we noticed across photos
    patterns_noticed: list[str] = []

    # Specific emotional moments we spotted
    emotional_moments: list[EmotionalMoment] = []

    # Personalized creative suggestions
    creative_sparks: list[CreativeSpark] = []

    # Per-image details with cross-image connections
    image_details: list[ImageDetail] = []

    # Raw analysis for debugging/advanced use
    raw_analysis: Optional[dict] = None

    # Legacy fields for backwards compatibility
    categories: Optional[dict[str, int]] = None
    suggestions: Optional[list[str]] = None


# =============================================================================
# Character Creation Request/Response Models
# =============================================================================

class CreateCharacterRequest(BaseModel):
    """Request to create an anime character from reference photos."""
    character_info: dict  # LifeCharacter data from gallery analysis
    selected_photo_paths: list[str]  # 3 photo paths for reference
    style: str = "anime"
    name: Optional[str] = None
    persona: Optional[str] = None  # User-provided persona (one line)
    pronouns: Optional[str] = "they"  # he, she, they
    session_id: Optional[str] = None


class GeneratedImage(BaseModel):
    """A generated image variant."""
    variant: str  # "full_body" or "portrait"
    url: str  # Relative URL like "/assets/outputs/characters/abc_full_body.png"


class CreateCharacterResponse(BaseModel):
    """Response with generated character images."""
    character_id: str
    name: str
    style: str
    generated_images: list[GeneratedImage]
    generation_time_seconds: float


# =============================================================================
# Manga Generation Request/Response Models
# =============================================================================

class CharacterInfo(BaseModel):
    """Character reference for manga generation."""
    name: str  # Character name
    image_url: str  # URL to character reference image


class CreateMangaRequest(BaseModel):
    """Request to create a multi-panel manga with characters (max 2)."""
    characters: list[CharacterInfo]  # 1-2 characters with name and image URL
    panel_count: int  # Number of panels (2-6)
    story_beats: list[str]  # Visual description for each panel (behind-the-scenes)
    dialogues: list[str] = []  # Optional dialogue for each panel (displayed to user)
    style: str = "manga"  # Visual style: manga, webtoon, chibi, ghibli
    session_id: Optional[str] = None


class MangaPanelResponse(BaseModel):
    """A single manga panel in API response."""
    index: int
    story_beat: str  # Behind-the-scenes description (for tech flow)
    dialogue: str = ""  # 0-2 lines of dialogue to display under panel
    image_url: str


class CreateMangaResponse(BaseModel):
    """Response with generated manga panels."""
    manga_id: str
    character_name: str
    style: str
    panel_count: int
    panels: list[MangaPanelResponse]
    generation_time_seconds: float


class AnimateStoryRequest(BaseModel):
    """Request to animate a manga into a video using Veo 3.1-fast native audio."""
    manga_id: str
    panels: list[MangaPanelResponse]  # Panel data from manga generation
    characters: list[CharacterInfo]  # Character info
    character_data: list[dict] = []  # Optional: analysis/concept for character persona
    character_sheets: dict[str, str] = {}  # {name: full_body_image_url} for Veo reference
    session_id: Optional[str] = None


# =============================================================================
# Story Options Generation Request/Response Models
# =============================================================================

class StoryOptionBeats(BaseModel):
    """A story option with beats for manga generation."""
    emoji: str
    label: str
    beats: list[str]  # 4 story beats for manga panels


class SceneOption(BaseModel):
    """A scene option for scene generation."""
    emoji: str
    label: str
    description: str


class GenerateStoryOptionsRequest(BaseModel):
    """Request to generate personalized story options using Gemini."""
    character_name: str
    character_type: str  # pet, person, etc.
    character_description: str  # who_they_are from analysis
    character_traits: str  # what_you_notice from analysis
    story_type: str  # manga
    initial_concept: Optional[str] = None  # User-provided concept to generate beats for


class GenerateStoryOptionsResponse(BaseModel):
    """Response with Gemini-generated story options."""
    story_type: str
    character_name: str
    options: list[dict]  # Either StoryOptionBeats or SceneOption format
    custom_option: dict  # The "My own idea..." option


# =============================================================================
# Gallery Analysis Prompt - Deep, Personal, Story-Aware
# =============================================================================

GALLERY_ANALYSIS_PROMPT = """
You are about to look through someone's personal media gallery — a mix of photos AND videos. These aren't just files — they're windows into someone's life, their loves, their memories.

Every gallery tells a unique story. Your job is to SEE and HEAR that story and respond with warmth.

## CRITICAL: Media Indexing

Each item is labeled `[Media X: filename]` (0-based). The filename tells you what the item is.
- `[Media 11: dog_01.webp]` → index 11 is a dog photo
- `[Media 3: cat_clip.mp4 (video)]` → index 3 is a cat video
- `[Media 0: photo_abc123.jpeg (your upload)]` → index 0 is a user-uploaded photo

Items marked **(your upload)** were actively added by the user. They chose these specifically, so **always** include subjects from uploaded media as life_characters — even if they appear in only 1-3 items. The user uploaded them because they matter.

USE THE FILENAMES to verify your indices! If you're listing a dog character's media_indices and you know the dog photos are named dog_01, dog_02, etc., check the labels to find their exact index numbers.

For example:
- You see a dog in [Media 11: dog_01.webp], [Media 12: dog_02.webp], [Media 13: dog_03.webp], [Media 22: dog_04.webp], [Media 23: dog_05.webp] → media_indices: [11, 12, 13, 22, 23]

⚠️ ALWAYS cross-check: look at the [Media X: filename] label to confirm the index. Do NOT guess or estimate. The filename is your ground truth.

## How to Analyze

**1. Look for recurring characters across ALL media (photos AND videos):**
- Identify pets and people who appear in MULTIPLE items — photos, videos, or both.
- If you see the same cat in photos AND hear it meowing in a video — that's the same character. Include the video index!
- Create a life_character entry for EACH distinct individual.
- Prioritize: user uploads first, then pets, then people, then recurring objects.
- **User uploads are MANDATORY**: Any person, pet, or subject in items tagged "(your upload)" MUST get their own life_character entry. The user specifically added these — never ignore them.
- IMPORTANT: Check EVERY [Media X] label. Videos count!

**2. Notice patterns across time:**
- The same cat in different seasons, different contexts
- A favorite place they keep returning to
- How relationships and lives evolve across the gallery

**3. See the emotional moments:**
- Not "people at beach" but "a sun-drenched afternoon, everyone laughing, probably a vacation that mattered"
- Not "cat on couch" but "a quiet moment of companionship, the soft afternoon light says it's their regular spot"

**4. For videos — listen to what the AUDIO reveals:**
- Speech/dialogue: What are people saying? What language? What tone?
- Ambient sounds: traffic noise, nature, music, kitchen sounds, animal vocalizations
- Audio + visual together tell a richer story than either alone
- Note specific audio details (e.g., "you can hear the cat purring", "street musicians playing", "the baby giggling")
- IMPORTANT: Mention what you heard in videos in your what_you_notice and opening_reaction!

**5. Recognize what makes this gallery THEIRS:**
- What do they clearly love capturing?
- What moments do they choose to record?
- What does this collection — photos and videos together — say about who they are?

## Your Response

Respond with warmth, like a friend who's been shown these precious memories. Mention something from the videos too — show that you listened, not just looked.

Return JSON in this format:
{
    "opening_reaction": "<Your warm first reaction. Mention something you SAW in a photo AND something you HEARD in a video. 2-3 sentences.>",

    "life_characters": [
        // Each entry = ONE INDIVIDUAL. Include video indices!
        {
            "name_suggestion": "<Suggest a name>",
            "who_they_are": "<Describe this being>",
            "appearances": <count across ALL media — photos + videos>,
            "what_you_notice": "<Something specific. If they appear in a video, mention what you heard/saw in it!>",
            "type": "pet|person|recurring_subject",
            "media_indices": [0, 1, 2, 3]  // ALL media — photos AND videos. Videos are just as important as photos!
        }
    ],

    "meaningful_places": [
        {
            "place_description": "<What/where is this?>",
            "why_it_seems_to_matter": "<Why does this place appear in their gallery?>",
            "mood": "<What feeling does it evoke?>",
            "appearances": <count across all media>,
            "media_indices": [7, 8, 10]  // Include video indices where this place appears!
        }
    ],

    "gallery_story": "<2-3 sentences about the story of this gallery. Reference both photos and videos.>",

    "patterns_noticed": [
        "<Pattern across the gallery>",
        "<Another pattern>"
    ],

    "emotional_moments": [
        {
            "media_index": <which item — can be a photo or video>,
            "what_you_see": "<The emotional read — for videos, include what you heard>"
        }
    ],

    "creative_sparks": [
        {
            "idea": "<A creative suggestion personal to THIS gallery>",
            "why_this_fits": "<Why this matches their life>",
            "based_on": "<What inspired this — can reference videos too>"
        }
    ],

    "media_details": [
        {
            "index": 0,
            "type": "image|video",
            "primary_subject": "<Who/what is the main focus>",
            "emotional_read": "<What moment or feeling — for videos, what did you hear?>",
            "connections": "<How does this connect to other items?>"
        }
    ]
}

Remember: You're not categorizing files. You're witnessing someone's life through photos AND videos, and responding with the warmth that deserves.
"""

# Wrapper for streaming endpoint — asks Gemini to output reactions before JSON
STREAMING_REACTION_PREFIX = """IMPORTANT RESPONSE FORMAT — follow this exactly:

PART 1 — FIRST IMPRESSIONS (output these FIRST):
As you look through this gallery, share your genuine reactions as you discover what's in it.
Output 4-8 brief reactions, one per line, each starting with exactly "REACT:" — like a friend who's excited to flip through someone's photos:

REACT: Oh, this orange tabby is absolutely the star of this gallery!
REACT: The beach sunset shots — you clearly love golden hour.
REACT: That little dog has the most expressive face I've ever seen!

Be warm, genuine, and specific about what you actually see. One sentence each. React to the most striking things.

PART 2 — FULL ANALYSIS (output AFTER all reactions):
Output your complete JSON analysis wrapped in ```json and ``` code fence markers.

Here are the analysis instructions:

"""


def _extract_json_from_text(text: str) -> dict:
    """Extract JSON from text that may contain reactions and code fences."""
    # Try to find JSON in code fences first
    fence_match = re.search(r'```json\s*\n([\s\S]*?)\n\s*```', text)
    if fence_match:
        return json.loads(fence_match.group(1))

    # Fallback: find the outermost { ... } block
    brace_start = text.find('{')
    if brace_start == -1:
        raise ValueError("No JSON found in response")

    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return json.loads(text[brace_start:i + 1])

    raise ValueError("Unbalanced JSON in response")


def _associate_videos_with_subjects(analysis: dict, media_items: list) -> dict:
    """
    Post-process: ensure video indices appear in character/place media_indices.

    Gemini sometimes omits video indices even when characters appear in videos.
    This associates each video with the character/place whose photo indices are
    nearest in the gallery sequence (videos are grouped with related photos).
    """
    video_indices = [i for i, item in enumerate(media_items) if item.type == "video"]
    if not video_indices:
        return analysis

    for vi in video_indices:
        # Find photo indices near this video (biased backward — videos follow their group)
        nearby = set()
        for offset in range(-3, 1):
            idx = vi + offset
            if 0 <= idx < len(media_items) and media_items[idx].type == "image":
                nearby.add(idx)

        # Associate with the character/place that has the MOST nearby photos
        # (avoids false matches when groups are close together)
        best_char = None
        best_char_overlap = 0
        for char in analysis.get("life_characters", []):
            indices = char.get("media_indices", char.get("image_indices", []))
            if vi in indices:
                best_char = None  # Already associated
                break
            overlap = sum(1 for pi in indices if pi in nearby)
            if overlap > best_char_overlap:
                best_char_overlap = overlap
                best_char = char

        if best_char and best_char_overlap > 0:
            indices = best_char.get("media_indices", best_char.get("image_indices", []))
            indices.append(vi)
            best_char["media_indices"] = indices
            logger.info(f"[STREAM] Auto-associated video {vi} with character '{best_char.get('name_suggestion', '?')}' ({best_char_overlap} nearby)")

        # Same for places
        best_place = None
        best_place_overlap = 0
        for place in analysis.get("meaningful_places", []):
            indices = place.get("media_indices", place.get("image_indices", []))
            if vi in indices:
                best_place = None
                break
            overlap = sum(1 for pi in indices if pi in nearby)
            if overlap > best_place_overlap:
                best_place_overlap = overlap
                best_place = place

        if best_place and best_place_overlap > 0:
            indices = best_place.get("media_indices", best_place.get("image_indices", []))
            indices.append(vi)
            best_place["media_indices"] = indices
            logger.info(f"[STREAM] Auto-associated video {vi} with place '{best_place.get('place_description', '?')}' ({best_place_overlap} nearby)")

    return analysis


def _unwrap_analysis(analysis) -> dict:
    """Unwrap analysis if Gemini returned a list instead of a dict."""
    if isinstance(analysis, list):
        logger.warning(f"[Analysis] Gemini returned a list ({len(analysis)} items), unwrapping first element")
        return analysis[0] if analysis and isinstance(analysis[0], dict) else {}
    if not isinstance(analysis, dict):
        logger.warning(f"[Analysis] Unexpected analysis type: {type(analysis)}")
        return {}
    return analysis


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/")
async def root():
    """Serve the demo HTML."""
    demo_path = Path(__file__).parent / "demo.html"
    if demo_path.exists():
        return FileResponse(demo_path)
    return {"message": "Creative Universe API", "status": "running"}


@app.get("/styles.css")
async def styles():
    """Serve the CSS file."""
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        return FileResponse(css_path, media_type="text/css")
    return {"error": "styles.css not found"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "model": GEMINI_MODEL}


# =============================================================================
# Agent Chat Proxy (so frontend uses backend's API key)
# =============================================================================

class AgentChatRequest(BaseModel):
    """Request for agent chat proxy."""
    contents: list  # Conversation history
    system_instruction: str  # System prompt
    tools: list  # Function declarations


@app.post("/api/agent/chat")
async def agent_chat(request: AgentChatRequest):
    """
    Proxy Gemini API calls so frontend doesn't need API key.
    Uses the backend's GOOGLE_API_KEY from .env.
    """
    try:
        # Log incoming request for debugging
        logger.info(f"Agent chat request: {len(request.contents)} messages")
        for i, msg in enumerate(request.contents):
            role = msg.get("role", "?")
            parts_summary = []
            for p in msg.get("parts", []):
                if "text" in p:
                    parts_summary.append(f"text({len(p['text'])})")
                elif "functionCall" in p:
                    parts_summary.append(f"funcCall({p['functionCall']['name']})")
                elif "functionResponse" in p:
                    parts_summary.append(f"funcResp({p['functionResponse']['name']})")
            logger.info(f"  [{i}] role={role}, parts={parts_summary}")

        # Build the request for Gemini
        gemini_contents = []
        for msg in request.contents:
            parts = []
            for part in msg.get("parts", []):
                if "text" in part:
                    parts.append(types.Part.from_text(text=part["text"]))
                elif "functionCall" in part:
                    # Check if thought_signature is included (required by Gemini 3)
                    if "thoughtSignature" in part:
                        import base64
                        thought_sig = base64.b64decode(part["thoughtSignature"])
                        parts.append(types.Part(
                            function_call=types.FunctionCall(
                                name=part["functionCall"]["name"],
                                args=part["functionCall"]["args"]
                            ),
                            thought_signature=thought_sig
                        ))
                    else:
                        parts.append(types.Part.from_function_call(
                            name=part["functionCall"]["name"],
                            args=part["functionCall"]["args"]
                        ))
                elif "functionResponse" in part:
                    parts.append(types.Part.from_function_response(
                        name=part["functionResponse"]["name"],
                        response=part["functionResponse"]["response"]
                    ))
            gemini_contents.append(types.Content(
                role=msg.get("role", "user"),
                parts=parts
            ))

        # Build tools config
        tools_config = None
        if request.tools:
            tools_config = types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("parameters")
                ) for t in request.tools
            ])

        # Call Gemini (always temp=1 per project convention)
        # Use thinking_level="low" for fast agent responses
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=gemini_contents,
            config=types.GenerateContentConfig(
                system_instruction=request.system_instruction,
                tools=[tools_config] if tools_config else None,
                temperature=1.0,  # Always 1.0 per project convention
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            )
        )

        # Log raw response for debugging
        logger.info(f"Agent raw response: {response}")

        # Convert response to JSON-serializable format
        result = {
            "candidates": []
        }

        if response.candidates:
            logger.info(f"Agent got {len(response.candidates)} candidates")
            for i, candidate in enumerate(response.candidates):
                # Check for malformed function call
                if candidate.finish_reason and str(candidate.finish_reason) == "FinishReason.MALFORMED_FUNCTION_CALL":
                    logger.warning(f"MALFORMED_FUNCTION_CALL detected - Gemini tried to call a function but failed")
                    # Return error so frontend can handle it
                    raise HTTPException(status_code=400, detail="Gemini returned a malformed function call. This usually means the function parameters were too complex.")

                has_content = candidate.content is not None
                has_parts = has_content and candidate.content.parts is not None
                parts_count = len(candidate.content.parts) if has_parts else 0
                logger.info(f"Candidate {i}: role={candidate.content.role if has_content else 'none'}, parts={parts_count}, finish_reason={candidate.finish_reason}")
                candidate_data = {
                    "content": {
                        "role": candidate.content.role if candidate.content else "model",
                        "parts": []
                    }
                }
                if candidate.content and candidate.content.parts:
                    for j, part in enumerate(candidate.content.parts):
                        logger.info(f"Part {j}: text={bool(part.text)}, func={bool(part.function_call)}")
                        if part.text:
                            candidate_data["content"]["parts"].append({"text": part.text})
                            logger.info(f"TEXT RESPONSE: {part.text[:500]}")
                        elif part.function_call:
                            func_part = {
                                "functionCall": {
                                    "name": part.function_call.name,
                                    "args": dict(part.function_call.args) if part.function_call.args else {}
                                }
                            }
                            # Include thought_signature if present (required by Gemini 3 for function responses)
                            if hasattr(part, 'thought_signature') and part.thought_signature:
                                import base64
                                func_part["thoughtSignature"] = base64.b64encode(part.thought_signature).decode('utf-8')
                            candidate_data["content"]["parts"].append(func_part)
                            logger.info(f"FUNCTION CALL: {part.function_call.name} args={part.function_call.args}")
                result["candidates"].append(candidate_data)
        else:
            logger.warning("Agent response: No candidates returned")

        logger.info(f"Returning result: {result}")
        return result

    except Exception as e:
        logger.error(f"Agent chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Debug Session Endpoints (for Claude Code introspection)
# =============================================================================

class DebugSessionUpdate(BaseModel):
    """Update to session state from browser."""
    session_id: str
    context: Optional[dict] = None
    conversation_history: Optional[list] = None
    pending_story: Optional[dict] = None
    saved_characters: Optional[list] = None
    generated_characters: Optional[list] = None
    analysis_result: Optional[dict] = None
    last_user_action: Optional[str] = None
    last_agent_response: Optional[dict] = None
    # NEW: UI state for full visibility
    current_display: Optional[dict] = None  # Currently displayed card
    chat_messages_ui: Optional[list] = None  # Recent messages from DOM


@app.post("/api/debug/session")
async def update_debug_session(update: DebugSessionUpdate):
    """
    Browser posts session state here for Claude Code to inspect.

    Call this from the browser after each agent interaction to keep
    the debug state current.
    """
    state = _get_debug_session(update.session_id)
    state["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

    # Update fields that were provided
    if update.context is not None:
        state["context"] = update.context
    if update.conversation_history is not None:
        state["conversation_history"] = update.conversation_history
    if update.pending_story is not None:
        state["pending_story"] = update.pending_story
    if update.saved_characters is not None:
        state["saved_characters"] = update.saved_characters
    if update.generated_characters is not None:
        state["generated_characters"] = update.generated_characters
    if update.analysis_result is not None:
        state["analysis_result"] = update.analysis_result
    if update.last_user_action is not None:
        state["last_user_action"] = update.last_user_action
    if update.last_agent_response is not None:
        state["last_agent_response"] = update.last_agent_response
    if update.current_display is not None:
        state["current_display"] = update.current_display
    if update.chat_messages_ui is not None:
        state["chat_messages_ui"] = update.chat_messages_ui

    logger.info(f"Debug session updated: {update.session_id}")
    return {"status": "ok", "updated_at": state["last_updated"]}


@app.get("/api/debug/session")
async def get_debug_session(session_id: Optional[str] = None):
    """
    Claude Code can GET this endpoint to inspect current browser session state.
    Pass ?session_id=... for a specific session, or omit for all active sessions.
    """
    if session_id:
        state = _get_debug_session(session_id)
        return {
            "status": "ok",
            "session": state,
            "summary": {
                "has_session": True,
                "last_updated": state["last_updated"],
                "conversation_turns": len(state.get("conversation_history", [])),
                "saved_characters": len(state.get("saved_characters", [])),
                "has_pending_story": state.get("pending_story") is not None,
                "last_action": state.get("last_user_action"),
            }
        }
    # Return summary of all active sessions
    return {
        "status": "ok",
        "active_sessions": len(_debug_sessions),
        "sessions": {
            sid: {
                "last_updated": s.get("last_updated"),
                "conversation_turns": len(s.get("conversation_history", [])),
            }
            for sid, s in _debug_sessions.items()
        },
    }


@app.get("/api/debug/session/summary")
async def get_debug_session_summary(session_id: Optional[str] = None):
    """
    Quick summary of session state for Claude Code.
    Pass ?session_id=... for a specific session, or omit for all.
    """
    if session_id:
        state = _get_debug_session(session_id)
        return {
            "session_id": state.get("session_id"),
            "last_updated": state.get("last_updated"),
            "conversation_turns": len(state.get("conversation_history", [])),
            "saved_characters": [c.get("name") for c in state.get("saved_characters", [])],
            "generated_characters": [c.get("name") for c in state.get("generated_characters", [])],
            "pending_story": state.get("pending_story"),
            "last_user_action": state.get("last_user_action"),
            "last_agent_response_type": state.get("last_agent_response", {}).get("type") if state.get("last_agent_response") else None,
        }
    return {
        "active_sessions": len(_debug_sessions),
        "session_ids": list(_debug_sessions.keys()),
    }


# =============================================================================
# Debug Log Endpoints (for Claude Code to inspect server logs)
# =============================================================================

@app.get("/api/debug/logs")
async def get_debug_logs(lines: int = 100):
    """
    Get recent server logs for Claude Code debugging.

    Args:
        lines: Number of recent log lines to return (default 100, max 500)

    Example usage from Claude Code:
        curl http://localhost:8000/api/debug/logs?lines=50
    """
    lines = min(lines, 500)  # Cap at 500 lines

    if not _log_file.exists():
        return {"status": "error", "message": "Log file not found"}

    try:
        with open(_log_file, "r") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {
            "status": "ok",
            "log_file": str(_log_file),
            "total_lines": len(all_lines),
            "returned_lines": len(recent_lines),
            "logs": [line.strip() for line in recent_lines]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/debug/logs/errors")
async def get_debug_log_errors(lines: int = 50):
    """
    Get only ERROR and WARNING lines from server logs.

    Useful for quickly finding issues without reading full logs.

    Example usage from Claude Code:
        curl http://localhost:8000/api/debug/logs/errors
    """
    lines = min(lines, 200)

    if not _log_file.exists():
        return {"status": "error", "message": "Log file not found"}

    try:
        with open(_log_file, "r") as f:
            all_lines = f.readlines()

        # Filter for errors and warnings
        error_lines = [
            line.strip() for line in all_lines
            if "ERROR" in line or "WARNING" in line or "Exception" in line
        ]

        recent_errors = error_lines[-lines:] if len(error_lines) > lines else error_lines

        return {
            "status": "ok",
            "log_file": str(_log_file),
            "total_errors": len(error_lines),
            "returned_errors": len(recent_errors),
            "errors": recent_errors
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/debug/logs/list")
async def list_debug_logs():
    """
    List all available log files for this project.

    Returns log files sorted by date (newest first).
    """
    try:
        log_files = sorted(LOGS_DIR.glob("server_*.log"), reverse=True)
        return {
            "status": "ok",
            "logs_dir": str(LOGS_DIR),
            "current_log": str(_log_file),
            "available_logs": [
                {
                    "filename": f.name,
                    "path": str(f),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime))
                }
                for f in log_files[:10]  # Last 10 logs
            ]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# =============================================================================
# Media Upload Endpoint
# =============================================================================

# File size limits
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024   # 50MB

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.webm'}


@app.post("/api/upload-media")
async def upload_media(
    file: UploadFile = File(...),
    session_id: str = Form(default=""),
):
    """Upload an image or video to the session-scoped directory."""
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    # Validate extension
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    is_video = ext in VIDEO_EXTENSIONS
    is_image = ext in IMAGE_EXTENSIONS

    if not is_video and not is_image:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Read and validate size
    content = await file.read()
    max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(content)} bytes (max: {max_size})"
        )

    # Save to session-scoped directory
    session_dir = get_session_output_dir(session_id) / "uploads"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Generate neutral filename (avoids confusing Gemini with original names like "Generated Image...")
    tag = uuid.uuid4().hex[:8]
    prefix = "clip" if is_video else "photo"
    safe_name = f"{prefix}_{tag}{ext}"
    save_path = session_dir / safe_name

    with open(save_path, "wb") as f:
        f.write(content)

    # Build URL relative to assets mount
    assets_root = Path(__file__).parent.parent / "assets"
    try:
        rel = save_path.resolve().relative_to(assets_root.resolve())
        url = f"/assets/{rel}"
    except ValueError:
        url = f"/assets/outputs/sessions/{session_id}/uploads/{safe_name}"

    logger.info(f"Uploaded {'video' if is_video else 'image'}: {save_path.name} ({len(content)} bytes)")

    return {
        "url": url,
        "filename": safe_name,
        "type": "video" if is_video else "image",
        "size": len(content),
    }


# =============================================================================
# Gallery Analysis Endpoint
# =============================================================================

@app.post("/api/analyze-gallery", response_model=GalleryAnalysisResponse)
async def analyze_gallery(request: GalleryAnalysisRequest):
    """
    Analyze a gallery of photos and videos using Gemini 3 Flash.

    This endpoint:
    1. Loads all provided media paths (images inline, videos via Files API)
    2. Sends them to Gemini 3 for batch analysis
    3. Returns structured understanding with creative suggestions
    """
    # Support both legacy (photos-only) and new (mixed media) format
    media_items: list[MediaItem] = []
    if request.media:
        media_items = request.media
    elif request.photos:
        media_items = [MediaItem(path=p, type="image") for p in request.photos]

    if not media_items:
        raise HTTPException(status_code=400, detail="No media provided")

    logger.info(f"Analyzing gallery with {len(media_items)} items")

    # Resolve media paths and build content parts
    base_dir = Path(__file__).parent.parent  # project root
    media_parts = []
    uploaded_video_files = []  # Track for cleanup

    image_mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }

    loaded_count = 0
    for idx, item in enumerate(media_items):
        media_path = item.path
        media_type = item.type
        is_uploaded = item.uploaded

        # Handle various path formats from the demo
        if media_path.startswith('../'):
            resolved_path = base_dir / media_path.replace('../', '')
        elif media_path.startswith('/assets/'):
            resolved_path = base_dir / media_path.lstrip('/')
        else:
            resolved_path = base_dir / "assets" / "demo_photos" / media_path

        if not resolved_path.exists():
            logger.warning(f"Media not found: {resolved_path}")
            continue

        # Validate file extension
        suffix = resolved_path.suffix.lower()
        if media_type == "image" and suffix not in image_mime_types:
            logger.warning(f"Unsupported image format [{idx}]: {suffix} ({resolved_path.name})")
            continue

        if media_type == "video":
            # Upload video via Gemini Files API for processing
            try:
                video_file = client.files.upload(file=str(resolved_path))
                # Poll until processing is complete
                while video_file.state.name == "PROCESSING":
                    await asyncio.sleep(2)
                    video_file = client.files.get(name=video_file.name)

                if video_file.state.name == "ACTIVE":
                    # Label with index + filename so Gemini can cross-reference
                    upload_tag = ", your upload" if is_uploaded else ""
                    media_parts.append(
                        types.Part.from_text(text=f"[Media {idx}: {resolved_path.name} (video{upload_tag})]")
                    )
                    media_parts.append(
                        types.Part.from_uri(
                            file_uri=video_file.uri,
                            mime_type=video_file.mime_type,
                        )
                    )
                    uploaded_video_files.append(video_file.name)
                    loaded_count += 1
                    logger.info(f"Uploaded video [{idx}]: {resolved_path.name}")
                else:
                    logger.warning(f"Video processing failed: {resolved_path.name} state={video_file.state.name}")
            except Exception as e:
                logger.warning(f"Failed to upload video {resolved_path}: {e}")
        else:
            # Image: inline bytes
            try:
                with open(resolved_path, "rb") as f:
                    image_data = f.read()

                mime_type = image_mime_types.get(suffix, "image/jpeg")

                # Label with index + filename so Gemini can cross-reference
                upload_tag = " (your upload)" if is_uploaded else ""
                media_parts.append(
                    types.Part.from_text(text=f"[Media {idx}: {resolved_path.name}{upload_tag}]")
                )
                media_parts.append(
                    types.Part.from_bytes(data=image_data, mime_type=mime_type)
                )
                loaded_count += 1
                logger.debug(f"Loaded image [{idx}]: {resolved_path.name}")
            except Exception as e:
                logger.warning(f"Failed to load {resolved_path}: {e}")

    if loaded_count == 0:
        raise HTTPException(status_code=400, detail="No valid media found")

    image_count = sum(1 for item in media_items if item.type == "image")
    video_count = sum(1 for item in media_items if item.type == "video")
    logger.info(f"Loaded {loaded_count}/{len(media_items)} items ({image_count} images + {video_count} videos), sending to Gemini 3...")

    try:
        # Build content with all media + prompt
        contents = media_parts + [GALLERY_ANALYSIS_PROMPT]

        # Call Gemini 3 Flash
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=1.0,  # Always 1.0 per project convention
                response_mime_type="application/json",
            ),
        )

        # Parse response
        analysis = _unwrap_analysis(json.loads(response.text))
        logger.info(f"Analysis complete - Opening: {analysis.get('opening_reaction', '')[:50]}...")

        # Which media indices are user uploads
        uploaded_indices = {idx for idx, item in enumerate(media_items) if item.uploaded}

        # Parse life characters (accept both media_indices and image_indices)
        life_characters = []
        for char in analysis.get("life_characters", []):
            try:
                indices = char.get("media_indices", char.get("image_indices", []))
                life_characters.append(LifeCharacter(
                    name_suggestion=char.get("name_suggestion", ""),
                    who_they_are=char.get("who_they_are", ""),
                    appearances=char.get("appearances", 1),
                    what_you_notice=char.get("what_you_notice", ""),
                    type=char.get("type", "unknown"),
                    image_indices=indices,
                    has_uploaded_media=bool(set(indices) & uploaded_indices),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse life character: {e}")

        # Parse meaningful places (accept both media_indices and image_indices)
        meaningful_places = []
        for place in analysis.get("meaningful_places", []):
            try:
                indices = place.get("media_indices", place.get("image_indices", []))
                meaningful_places.append(MeaningfulPlace(
                    place_description=place.get("place_description", ""),
                    why_it_seems_to_matter=place.get("why_it_seems_to_matter", ""),
                    mood=place.get("mood", ""),
                    appearances=place.get("appearances", 1),
                    image_indices=indices,
                    has_uploaded_media=bool(set(indices) & uploaded_indices),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse meaningful place: {e}")

        # Parse emotional moments (accept both media_index and photo_index)
        emotional_moments = []
        for moment in analysis.get("emotional_moments", []):
            try:
                idx = moment.get("media_index", moment.get("photo_index", 0))
                emotional_moments.append(EmotionalMoment(
                    photo_index=idx,
                    what_you_see=moment.get("what_you_see", ""),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse emotional moment: {e}")

        # Parse creative sparks
        creative_sparks = []
        for spark in analysis.get("creative_sparks", []):
            try:
                creative_sparks.append(CreativeSpark(
                    idea=spark.get("idea", ""),
                    why_this_fits=spark.get("why_this_fits", ""),
                    based_on=spark.get("based_on", ""),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse creative spark: {e}")

        # Parse media/image details (accept both media_details and image_details)
        image_details = []
        details_list = analysis.get("media_details", analysis.get("image_details", []))
        for detail in details_list:
            try:
                image_details.append(ImageDetail(
                    index=detail.get("index", 0),
                    primary_subject=detail.get("primary_subject", ""),
                    emotional_read=detail.get("emotional_read", ""),
                    connections=detail.get("connections", ""),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse media detail: {e}")

        # Extract legacy suggestions for backwards compatibility
        legacy_suggestions = [spark.idea for spark in creative_sparks]

        result = GalleryAnalysisResponse(
            opening_reaction=analysis.get("opening_reaction", ""),
            life_characters=life_characters,
            meaningful_places=meaningful_places,
            gallery_story=analysis.get("gallery_story", ""),
            patterns_noticed=analysis.get("patterns_noticed", []),
            emotional_moments=emotional_moments,
            creative_sparks=creative_sparks,
            image_details=image_details,
            raw_analysis=analysis,
            # Legacy fields
            suggestions=legacy_suggestions,
        )

        # Cleanup uploaded video files (best-effort)
        for video_name in uploaded_video_files:
            try:
                client.files.delete(name=video_name)
                logger.debug(f"Cleaned up uploaded video: {video_name}")
            except Exception:
                pass

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response: {e}")
        logger.error(f"Raw response: {response.text}")
        raise HTTPException(status_code=500, detail="Failed to parse analysis response")

    except Exception as e:
        error_msg = str(e)
        if "INVALID_ARGUMENT" in error_msg or "Unable to process" in error_msg:
            logger.error(f"Gemini rejected media input ({loaded_count} items): {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Gemini could not process some media. Try removing corrupt or unsupported files. ({error_msg})"
            )
        logger.error(f"Gemini API error: {e}")
        raise HTTPException(status_code=500, detail=error_msg)

    finally:
        # Cleanup uploaded video files even on error
        for video_name in uploaded_video_files:
            try:
                client.files.delete(name=video_name)
            except Exception:
                pass


@app.post("/api/analyze-gallery-stream")
async def analyze_gallery_stream(request: GalleryAnalysisRequest):
    """
    Streaming gallery analysis using Server-Sent Events.

    Same logic as /api/analyze-gallery but streams progress updates
    as media items are loaded and processed. Useful for large galleries
    with many videos (each video requires Files API upload + polling).
    """
    # Support both legacy (photos-only) and new (mixed media) format
    media_items: list[MediaItem] = []
    if request.media:
        media_items = request.media
    elif request.photos:
        media_items = [MediaItem(path=p, type="image") for p in request.photos]

    if not media_items:
        raise HTTPException(status_code=400, detail="No media provided")

    image_count = sum(1 for item in media_items if item.type == "image")
    video_count = sum(1 for item in media_items if item.type == "video")
    upload_count = sum(1 for item in media_items if item.uploaded)
    logger.info(f"[STREAM] Analyzing gallery with {len(media_items)} items ({image_count} images, {video_count} videos, {upload_count} user uploads)")

    base_dir = Path(__file__).parent.parent
    image_mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }

    async def stream_events():
        """Generator that yields SSE events as gallery is processed."""
        # Phase 0: Start
        yield f"data: {json.dumps({'type': 'start', 'total': len(media_items), 'images': image_count, 'videos': video_count})}\n\n"

        # Phase 1: Load media items with progress
        media_parts = []
        uploaded_video_files = []
        loaded_count = 0
        videos_uploaded = 0

        for idx, item in enumerate(media_items):
            media_path = item.path
            media_type = item.type
            is_uploaded = item.uploaded

            # Resolve path
            if media_path.startswith('../'):
                resolved_path = base_dir / media_path.replace('../', '')
            elif media_path.startswith('/assets/'):
                resolved_path = base_dir / media_path.lstrip('/')
            else:
                resolved_path = base_dir / "assets" / "demo_photos" / media_path

            if not resolved_path.exists():
                logger.warning(f"[STREAM] Media not found: {resolved_path}")
                yield f"data: {json.dumps({'type': 'progress', 'index': idx, 'total': len(media_items), 'message': f'Skipped missing file: {resolved_path.name}'})}\n\n"
                continue

            # Validate extension for images
            suffix = resolved_path.suffix.lower()
            if media_type == "image" and suffix not in image_mime_types:
                logger.warning(f"[STREAM] Unsupported image format [{idx}]: {suffix}")
                continue

            if media_type == "video":
                videos_uploaded += 1
                yield f"data: {json.dumps({'type': 'progress', 'index': idx, 'total': len(media_items), 'message': f'Uploading video {videos_uploaded}...'})}\n\n"
                try:
                    video_file = client.files.upload(file=str(resolved_path))
                    while video_file.state.name == "PROCESSING":
                        await asyncio.sleep(2)
                        video_file = client.files.get(name=video_file.name)

                    if video_file.state.name == "ACTIVE":
                        upload_tag = ", your upload" if is_uploaded else ""
                        media_parts.append(types.Part.from_text(text=f"[Media {idx}: {resolved_path.name} (video{upload_tag})]"))
                        media_parts.append(types.Part.from_uri(
                            file_uri=video_file.uri,
                            mime_type=video_file.mime_type,
                        ))
                        uploaded_video_files.append(video_file.name)
                        loaded_count += 1
                        yield f"data: {json.dumps({'type': 'progress', 'index': idx, 'total': len(media_items), 'message': f'Video {videos_uploaded} ready'})}\n\n"
                        logger.info(f"[STREAM] Uploaded video [{idx}]: {resolved_path.name}")
                    else:
                        logger.warning(f"[STREAM] Video processing failed: {resolved_path.name}")
                        yield f"data: {json.dumps({'type': 'progress', 'index': idx, 'total': len(media_items), 'message': f'Video {videos_uploaded} failed to process'})}\n\n"
                except Exception as e:
                    logger.warning(f"[STREAM] Failed to upload video {resolved_path}: {e}")
                    yield f"data: {json.dumps({'type': 'progress', 'index': idx, 'total': len(media_items), 'message': f'Video {videos_uploaded} upload failed'})}\n\n"
            else:
                try:
                    with open(resolved_path, "rb") as f:
                        image_data = f.read()
                    mime_type = image_mime_types.get(suffix, "image/jpeg")
                    upload_tag = " (your upload)" if is_uploaded else ""
                    media_parts.append(types.Part.from_text(text=f"[Media {idx}: {resolved_path.name}{upload_tag}]"))
                    media_parts.append(types.Part.from_bytes(data=image_data, mime_type=mime_type))
                    loaded_count += 1
                    yield f"data: {json.dumps({'type': 'progress', 'index': idx, 'total': len(media_items), 'message': f'Loaded image {idx + 1}'})}\n\n"
                except Exception as e:
                    logger.warning(f"[STREAM] Failed to load {resolved_path}: {e}")

        if loaded_count == 0:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No valid media found'})}\n\n"
            return

        # Phase 2: Stream Gemini response with real-time reactions
        yield f"data: {json.dumps({'type': 'analyzing', 'message': 'Gemini is looking through your gallery...', 'loaded': loaded_count})}\n\n"

        try:
            # Use streaming with reaction prefix for interactive UX
            streaming_prompt = STREAMING_REACTION_PREFIX + GALLERY_ANALYSIS_PROMPT
            contents = media_parts + [streaming_prompt]

            full_text = ""
            buffer = ""
            in_json = False
            json_lines = []
            reaction_count = 0

            for chunk in client.models.generate_content_stream(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(temperature=1.0),
            ):
                chunk_text = ""
                try:
                    chunk_text = chunk.text or ""
                except Exception:
                    continue

                full_text += chunk_text
                buffer += chunk_text

                # Process complete lines from the stream
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    stripped = line.strip()

                    if stripped.startswith('REACT:'):
                        reaction = stripped[6:].strip()
                        if reaction:
                            reaction_count += 1
                            logger.info(f"[STREAM] Reaction {reaction_count}: {reaction[:80]}")
                            yield f"data: {json.dumps({'type': 'reaction', 'message': reaction, 'index': reaction_count})}\n\n"
                    elif stripped.startswith('```json'):
                        in_json = True
                        yield f"data: {json.dumps({'type': 'progress', 'message': 'Putting it all together...'})}\n\n"
                    elif stripped == '```' and in_json:
                        in_json = False
                    elif in_json:
                        json_lines.append(line)

            # Handle remaining buffer
            if buffer.strip():
                if in_json:
                    json_lines.append(buffer)

            # Parse JSON from the streamed response
            json_text = '\n'.join(json_lines)
            if not json_text.strip():
                # Fallback: extract JSON from full text (no code fences found)
                logger.warning("[STREAM] No code-fenced JSON found, extracting from full text")
                analysis = _extract_json_from_text(full_text)
            else:
                # Use raw_decode to ignore trailing content after the JSON object
                # (Gemini sometimes appends extra text after the closing brace)
                try:
                    decoder = json.JSONDecoder()
                    analysis, _ = decoder.raw_decode(json_text.strip())
                except json.JSONDecodeError:
                    # Last resort: extract from full text using brace-balancing
                    logger.warning("[STREAM] Code-fenced JSON parse failed, extracting from full text")
                    analysis = _extract_json_from_text(full_text)

            analysis = _unwrap_analysis(analysis)
            logger.info(f"[STREAM] Analysis complete ({reaction_count} reactions) - Opening: {analysis.get('opening_reaction', '')[:50]}...")

            # Which media indices are user uploads (for logging)
            uploaded_indices_log = {idx for idx, item in enumerate(media_items) if item.uploaded}

            # Log character indices and upload status
            for ci, char in enumerate(analysis.get("life_characters", [])):
                indices = char.get("media_indices", char.get("image_indices", []))
                has_upload = bool(set(indices) & uploaded_indices_log)
                logger.info(f"[STREAM] Character {ci} '{char.get('name_suggestion', '?')}': indices={indices}, has_uploaded_media={has_upload}")
            for pi, place in enumerate(analysis.get("meaningful_places", [])):
                indices = place.get("media_indices", place.get("image_indices", []))
                has_upload = bool(set(indices) & uploaded_indices_log)
                logger.info(f"[STREAM] Place {pi} '{place.get('place_description', '?')}': indices={indices}, has_uploaded_media={has_upload}")

            # Phase 3: Stream parsed results
            if analysis.get("opening_reaction"):
                yield f"data: {json.dumps({'type': 'opening', 'text': analysis['opening_reaction']})}\n\n"

            for char in analysis.get("life_characters", []):
                yield f"data: {json.dumps({'type': 'character', 'data': char})}\n\n"

            for place in analysis.get("meaningful_places", []):
                yield f"data: {json.dumps({'type': 'place', 'data': place})}\n\n"

            # Which media indices are user uploads
            uploaded_indices = {idx for idx, item in enumerate(media_items) if item.uploaded}

            # Parse the full result (same logic as non-streaming endpoint)
            life_characters = []
            for char in analysis.get("life_characters", []):
                try:
                    indices = char.get("media_indices", char.get("image_indices", []))
                    life_characters.append(LifeCharacter(
                        name_suggestion=char.get("name_suggestion", ""),
                        who_they_are=char.get("who_they_are", ""),
                        appearances=char.get("appearances", 1),
                        what_you_notice=char.get("what_you_notice", ""),
                        type=char.get("type", "unknown"),
                        image_indices=indices,
                        has_uploaded_media=bool(set(indices) & uploaded_indices),
                    ))
                except Exception as e:
                    logger.warning(f"[STREAM] Failed to parse life character: {e}")

            meaningful_places = []
            for place in analysis.get("meaningful_places", []):
                try:
                    indices = place.get("media_indices", place.get("image_indices", []))
                    meaningful_places.append(MeaningfulPlace(
                        place_description=place.get("place_description", ""),
                        why_it_seems_to_matter=place.get("why_it_seems_to_matter", ""),
                        mood=place.get("mood", ""),
                        appearances=place.get("appearances", 1),
                        image_indices=indices,
                        has_uploaded_media=bool(set(indices) & uploaded_indices),
                    ))
                except Exception as e:
                    logger.warning(f"[STREAM] Failed to parse meaningful place: {e}")

            emotional_moments = []
            for moment in analysis.get("emotional_moments", []):
                try:
                    m_idx = moment.get("media_index", moment.get("photo_index", 0))
                    emotional_moments.append(EmotionalMoment(
                        photo_index=m_idx,
                        what_you_see=moment.get("what_you_see", ""),
                    ))
                except Exception:
                    pass

            creative_sparks = []
            for spark in analysis.get("creative_sparks", []):
                try:
                    creative_sparks.append(CreativeSpark(
                        idea=spark.get("idea", ""),
                        why_this_fits=spark.get("why_this_fits", ""),
                        based_on=spark.get("based_on", ""),
                    ))
                except Exception:
                    pass

            image_details = []
            details_list = analysis.get("media_details", analysis.get("image_details", []))
            for detail in details_list:
                try:
                    image_details.append(ImageDetail(
                        index=detail.get("index", 0),
                        primary_subject=detail.get("primary_subject", ""),
                        emotional_read=detail.get("emotional_read", ""),
                        connections=detail.get("connections", ""),
                    ))
                except Exception:
                    pass

            legacy_suggestions = [spark.idea for spark in creative_sparks]

            result = GalleryAnalysisResponse(
                opening_reaction=analysis.get("opening_reaction", ""),
                life_characters=life_characters,
                meaningful_places=meaningful_places,
                gallery_story=analysis.get("gallery_story", ""),
                patterns_noticed=analysis.get("patterns_noticed", []),
                emotional_moments=emotional_moments,
                creative_sparks=creative_sparks,
                image_details=image_details,
                raw_analysis=analysis,
                suggestions=legacy_suggestions,
            )

            # Send complete result
            yield f"data: {json.dumps({'type': 'complete', 'analysis': result.model_dump()})}\n\n"

        except json.JSONDecodeError as e:
            logger.error(f"[STREAM] Failed to parse Gemini response: {e}")
            logger.error(f"[STREAM] Raw text (first 500): {full_text[:500]}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to parse analysis response'})}\n\n"
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[STREAM] Gemini API error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Analysis failed: {error_msg}'})}\n\n"
        finally:
            # Cleanup uploaded video files
            for video_name in uploaded_video_files:
                try:
                    client.files.delete(name=video_name)
                except Exception:
                    pass

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/create-character", response_model=CreateCharacterResponse)
async def create_character(request: CreateCharacterRequest):
    """
    Generate anime character images from reference photos.

    Takes 3 reference photos and a character info dict from gallery analysis,
    generates full_body and portrait images using Nano Banana Pro.
    """
    logger.info(f"Creating character with {len(request.selected_photo_paths)} reference photos")

    # Validate photo count (1-3 photos, more is better for consistency)
    if len(request.selected_photo_paths) < 1 or len(request.selected_photo_paths) > 3:
        raise HTTPException(
            status_code=400,
            detail=f"1-3 reference photos required, got {len(request.selected_photo_paths)}"
        )

    # Resolve photo paths to absolute paths
    base_dir = Path(__file__).parent.parent  # project root
    source_images = []

    for photo_path in request.selected_photo_paths:
        # Handle various path formats from the demo
        if photo_path.startswith('../'):
            # Legacy format: ../assets/demo_photos/...
            resolved = base_dir / photo_path.replace('../', '')
        elif photo_path.startswith('/assets/'):
            # Absolute URL format: /assets/demo_photos/...
            resolved = base_dir / photo_path.lstrip('/')
        else:
            # Just filename or relative path
            resolved = base_dir / photo_path

        if resolved.exists():
            source_images.append(resolved)
            logger.info(f"Resolved reference: {resolved}")
        else:
            logger.warning(f"Reference photo not found: {resolved}")

    if len(source_images) < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Could not find any valid reference photos"
        )

    # Determine character type from analysis
    char_info = request.character_info
    source_type = char_info.get("type", "pet")
    if source_type not in ["pet", "person"]:
        source_type = "pet"

    # Create Character object
    character = Character(
        name=request.name or char_info.get("name_suggestion", "Character"),
        persona=request.persona or "",  # User-provided persona
        source_images=source_images,
        source_type=source_type,
        style=request.style,
        analysis=char_info,  # Use life_character data as analysis
    )

    logger.info(f"Generating character: {character.name} ({character.source_type})")

    # Generate character sheet
    start_time = time.time()
    generator = CharacterGenerator(client=client)

    # Session-scoped output directory
    if request.session_id:
        session_out = get_session_output_dir(request.session_id)
        generator.output_dir = session_out / "characters"
        generator.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        generated_images = await generator.generate_character_sheet(character)
    except Exception as e:
        logger.error(f"Character generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

    generation_time = time.time() - start_time
    logger.info(f"Generation complete in {generation_time:.1f}s, got {len(generated_images)} images")

    if not generated_images:
        raise HTTPException(status_code=500, detail="No images generated")

    # Build response with relative URLs for the frontend
    assets_root = Path(__file__).parent.parent / "assets"
    response_images = []
    for variant, path in generated_images.items():
        try:
            rel = path.resolve().relative_to(assets_root.resolve())
            url = f"/assets/{rel}"
        except ValueError:
            url = f"/assets/outputs/characters/{path.name}"
        response_images.append(GeneratedImage(variant=variant, url=url))

    return CreateCharacterResponse(
        character_id=character.id,
        name=character.name,
        style=character.style,
        generated_images=response_images,
        generation_time_seconds=round(generation_time, 1),
    )


@app.post("/api/create-manga", response_model=CreateMangaResponse)
async def create_manga(request: CreateMangaRequest):
    """
    Generate a multi-panel manga with a character (non-streaming).

    Delegates to MangaGenerator skill for actual generation.
    For progressive display, use /api/create-manga-stream instead.
    """
    logger.info(f"Creating {request.panel_count}-panel {request.style} manga for {request.character_name}")

    # Validate inputs
    if request.panel_count < 2 or request.panel_count > 6:
        raise HTTPException(status_code=400, detail=f"Panel count must be 2-6, got {request.panel_count}")

    if len(request.story_beats) != request.panel_count:
        raise HTTPException(status_code=400, detail=f"Story beats must match panel count")

    if not request.character_image_url:
        raise HTTPException(status_code=400, detail="character_image_url is required")

    # Resolve character image path
    base_dir = Path(__file__).parent.parent
    if request.character_image_url.startswith('/assets/'):
        char_image_path = base_dir / request.character_image_url.lstrip('/')
    else:
        char_image_path = base_dir / "assets" / request.character_image_url

    if not char_image_path.exists():
        raise HTTPException(status_code=400, detail=f"Character image not found: {request.character_image_url}")

    try:
        generator = MangaGenerator(client=client)
        result = await generator.generate_manga(
            character_image_path=char_image_path,
            character_name=request.character_name,
            story_beats=request.story_beats,
            dialogues=request.dialogues,
            style=request.style,
        )

        return CreateMangaResponse(
            manga_id=result.manga_id,
            character_name=result.character_name,
            style=result.style,
            panel_count=len(result.panels),
            panels=[MangaPanelResponse(
                index=p.index,
                story_beat=p.story_beat,
                dialogue=p.dialogue,
                image_url=p.image_url,
            ) for p in result.panels],
            generation_time_seconds=result.generation_time_seconds,
        )

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate manga: {e}")
        raise HTTPException(status_code=500, detail=f"Manga generation failed: {str(e)}")


@app.post("/api/create-manga-stream")
async def create_manga_stream(request: CreateMangaRequest):
    """
    Generate a multi-panel manga with STREAMING - each panel is sent as it's generated.
    Uses Server-Sent Events (SSE) to progressively show panels.

    Supports 1-2 characters per manga. Each panel gets up to 3 reference images:
    - Character 1 reference (always)
    - Character 2 reference (if multi-character)
    - Previous panel (for continuity)

    Delegates to MangaGenerator skill for actual generation.
    """
    # Validate max 2 characters
    if len(request.characters) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 characters per manga")
    if len(request.characters) == 0:
        raise HTTPException(status_code=400, detail="At least 1 character required")

    char_names = " & ".join(c.name for c in request.characters)
    logger.info(f"[STREAM] Creating {request.panel_count}-panel {request.style} manga for {char_names}")

    # Resolve character image paths
    base_dir = Path(__file__).parent.parent
    character_refs = []
    for char in request.characters:
        if char.image_url.startswith('/assets/'):
            path = base_dir / char.image_url.lstrip('/')
        else:
            path = base_dir / "assets" / char.image_url
        character_refs.append({"name": char.name, "path": path})
        logger.info(f"[STREAM] Character: {char.name} -> {path}")

    # Create generator with shared client
    generator = MangaGenerator(client=client)

    # Session-scoped output directory
    if request.session_id:
        session_out = get_session_output_dir(request.session_id)
        generator.output_dir = session_out / "manga"
        generator.output_dir.mkdir(parents=True, exist_ok=True)
        generator.url_prefix = f"/assets/outputs/sessions/{request.session_id}/manga"

    async def stream_events():
        """Wrap skill streaming to SSE format."""
        async for event in generator.generate_manga_streaming(
            character_refs=character_refs,  # List of {name, path}
            story_beats=request.story_beats,
            dialogues=request.dialogues,
            style=request.style,
        ):
            yield f"data: {json.dumps({'type': event.type, **event.data})}\n\n"

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/animate-story-stream")
async def animate_story_stream(request: AnimateStoryRequest):
    """
    Animate a manga into a video with STREAMING progress updates.

    Pipeline:
    1. Voice selection from character persona
    2. TTS generation (get exact durations)
    3. Veo 3.1 clips (panel as keyframe, duration from TTS)
    4. FFmpeg composition

    Uses Server-Sent Events (SSE) to show progress.
    """
    logger.info(f"[ANIMATE] Starting animation for manga {request.manga_id} with {len(request.panels)} panels")

    # Build MangaResult from request data
    from skills.generate_manga.generate_manga import MangaResult, MangaPanel as MangaPanelData
    from pathlib import Path

    base_dir = Path(__file__).parent.parent

    # Convert panels to MangaPanel objects
    panels = []
    for p in request.panels:
        # Resolve image path from URL
        if p.image_url.startswith('/assets/'):
            image_path = base_dir / p.image_url.lstrip('/')
        else:
            image_path = base_dir / "assets" / p.image_url

        panels.append(MangaPanelData(
            index=p.index,
            story_beat=p.story_beat,
            dialogue=p.dialogue,
            image_path=image_path,
            image_url=p.image_url,
        ))

    manga_result = MangaResult(
        manga_id=request.manga_id,
        character_name=" & ".join(c.name for c in request.characters),
        style="manga",
        panels=panels,
    )

    # Build character data for voice selection
    characters = []
    for i, char in enumerate(request.characters):
        char_data = {
            "name": char.name,
            "source_type": "pet",  # Default, can be overridden
        }
        # Merge any additional character data (analysis, concept)
        if i < len(request.character_data):
            char_data.update(request.character_data[i])
        characters.append(char_data)

    # Resolve character sheet paths from URLs
    character_sheets = {}
    for name, url in request.character_sheets.items():
        if url:
            if url.startswith('/assets/'):
                sheet_path = base_dir / url.lstrip('/')
            else:
                sheet_path = base_dir / "assets" / url
            if sheet_path.exists():
                character_sheets[name] = sheet_path
                logger.info(f"[ANIMATE] Character sheet for {name}: {sheet_path}")

    # Create generator
    generator = AnimatedStoryGenerator()

    # Session-scoped output directories
    if request.session_id:
        session_out = get_session_output_dir(request.session_id)
        generator.output_dir = session_out / "animated_stories"
        generator.output_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(generator, 'composer') and generator.composer:
            generator.composer.output_dir = session_out / "final"
            generator.composer.output_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(generator, 'video') and generator.video:
            generator.video.output_dir = session_out / "videos"
            generator.video.output_dir.mkdir(parents=True, exist_ok=True)

    # Build character name and story summary for lyrics generation
    character_name = " & ".join(c.name for c in request.characters) if request.characters else ""
    story_summary = " → ".join(p.story_beat for p in request.panels if p.story_beat) or ""

    async def stream_events():
        """Wrap skill streaming to SSE format with global keepalive.

        The animation pipeline has multiple long-blocking steps (Veo clips,
        Remotion rendering) that can each take minutes. Without periodic SSE
        data, Cloudflare Tunnel kills the idle connection. This wrapper runs
        the generator in a background task, collects events via a queue, and
        sends keepalive pings every 10s during any silent gap.
        """
        import asyncio as _asyncio

        queue: _asyncio.Queue = _asyncio.Queue()
        KEEPALIVE_INTERVAL = 10  # seconds

        async def _producer():
            try:
                logger.info(f"[ANIMATE] Using music pipeline with {len(character_sheets)} character sheets")
                async for event in generator.generate_animated_story_with_music_streaming(
                    manga_result=manga_result,
                    characters=characters,
                    character_name=character_name,
                    story_summary=story_summary,
                    enable_lyrics=True,
                    clip_duration=4,
                ):
                    await queue.put(event)
            except Exception as e:
                logger.error(f"[ANIMATE] Pipeline error: {e}")
                from skills.generate_animated_story.generate_animated_story import AnimationStreamEvent
                await queue.put(AnimationStreamEvent('error', {'message': str(e)[:200]}))
            finally:
                await queue.put(None)  # sentinel

        producer_task = _asyncio.create_task(_producer())

        try:
            while True:
                try:
                    event = await _asyncio.wait_for(queue.get(), timeout=KEEPALIVE_INTERVAL)
                except _asyncio.TimeoutError:
                    # No event for KEEPALIVE_INTERVAL seconds — send keepalive
                    yield f": keepalive\n\n"
                    continue

                if event is None:
                    break  # producer done

                yield f"data: {json.dumps({'type': event.type, **event.data})}\n\n"
        finally:
            if not producer_task.done():
                producer_task.cancel()

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/generate-story-options", response_model=GenerateStoryOptionsResponse)
async def generate_story_options(request: GenerateStoryOptionsRequest):
    """
    Generate personalized story options using Gemini.

    This is the AGENTIC approach: Gemini decides what story options to show
    based on the character's attributes, NOT hardcoded if/else logic.

    If initial_concept is provided, generate story beats for THAT concept directly
    instead of generating multiple options.
    """
    logger.info(f"Generating {request.story_type} options for {request.character_name}")

    # If user provided a specific concept, generate beats for that concept directly
    if request.initial_concept and request.story_type == "manga":
        logger.info(f"Direct concept provided: {request.initial_concept}")
        prompt = f"""You are a storyboard artist for anime. The user has a specific story concept. Generate story beats for it.

CHARACTER:
- Name: {request.character_name}
- Type: {request.character_type}
- Description: {request.character_description}
- Personality: {request.character_traits}

USER'S STORY CONCEPT: "{request.initial_concept}"

Create a 4-shot storyboard that brings this concept to life:
- Setup → Action → Twist/Complication → Payoff
- {request.character_name} is the ONLY character
- Include cinematic camera angles (close-up, wide shot, low angle, etc.)
- Give {request.character_name} personality through dialogue

Return JSON with ONE option based on the user's concept:
{{
    "options": [
        {{
            "emoji": "<emoji matching the story tone>",
            "label": "<2-4 word title for their concept>",
            "beats": [
                {{
                    "description": "<SHOT 1: Camera angle + action + environment, 12-20 words>",
                    "dialogue": "<What {request.character_name} says/thinks, 1-8 words>"
                }},
                {{
                    "description": "<SHOT 2: The action unfolds>",
                    "dialogue": "<Reaction>"
                }},
                {{
                    "description": "<SHOT 3: Twist or escalation>",
                    "dialogue": "<Response>"
                }},
                {{
                    "description": "<SHOT 4: Resolution with emotion>",
                    "dialogue": "<Final line>"
                }}
            ]
        }}
    ]
}}

Make it fun and true to their concept: "{request.initial_concept}" """

    # Standard flow: generate 3 different story options
    elif request.story_type == "manga":
        prompt = f"""You are a storyboard artist for anime. Generate 3 short story ideas for this character.

CHARACTER:
- Name: {request.character_name}
- Type: {request.character_type}
- Description: {request.character_description}
- Personality: {request.character_traits}

STORYBOARD RULES:
- Each story is 4 shots that will become an anime sequence
- Stories are ACTION-DRIVEN with a mini plot: setup → action → twist/complication → payoff
- {request.character_name} is the ONLY character (no humans, no "you", no new characters)
- Non-human characters CAN and SHOULD speak! Give them personality through dialogue
- "SHOW, DON'T TELL" — no narration. Only what we SEE and what the character SAYS

SHOT DESCRIPTIONS should be CINEMATIC:
- Include camera angle: close-up, medium shot, wide shot, low angle, bird's eye, over-the-shoulder
- Describe the ACTION happening, not a static pose
- Rich visual details: lighting, environment, character expression/body language

DIALOGUE is what the character SAYS or THINKS:
- Short, punchy lines (1-8 words max)
- Reveals personality, emotion, or reaction
- Can be speech, inner thought, or expressive sounds
- NOT narration or description of what's happening

Generate 3 story ideas with different tones:
1. Comedic/mischievous (something goes hilariously wrong)
2. Adventurous/exciting (discovery, challenge, triumph)
3. Heartwarming/cozy (quiet moment with emotional payoff)

Return JSON:
{{
    "options": [
        {{
            "emoji": "<single emoji>",
            "label": "<2-4 word title>",
            "beats": [
                {{
                    "description": "<SHOT 1: Camera angle + {request.character_name}'s action + environment, 12-20 words>",
                    "dialogue": "<What {request.character_name} says/thinks, 1-8 words, or empty>"
                }},
                {{
                    "description": "<SHOT 2: The action/event unfolds>",
                    "dialogue": "<Reaction or response>"
                }},
                {{
                    "description": "<SHOT 3: Twist, complication, or escalation>",
                    "dialogue": "<Character's response>"
                }},
                {{
                    "description": "<SHOT 4: Resolution with clear emotion>",
                    "dialogue": "<Final line or reaction>"
                }}
            ]
        }}
    ]
}}

Be specific to {request.character_name}'s personality. Make each story feel like a mini anime episode."""
    else:
        prompt = f"""You are a creative illustration assistant. Generate 3 personalized scene ideas for this character.

CHARACTER INFO:
- Name: {request.character_name}
- Type: {request.character_type}
- Description: {request.character_description}
- Notable traits: {request.character_traits}

Generate 3 unique scene/illustration ideas that are:
1. Personalized to this specific character's traits and personality
2. Visually interesting and emotionally engaging
3. Each with a clear setting and mood

Return JSON in this exact format:
{{
    "options": [
        {{
            "emoji": "<single emoji that captures the scene mood>",
            "label": "<catchy 3-5 word scene title>",
            "description": "<Detailed scene description referencing the character by their description, ~15-20 words>"
        }},
        // ... 2 more options
    ]
}}

Make each scene unique and specifically tailored to what you know about {request.character_name}.
Consider their personality and traits when designing the scenes."""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=1.0,  # Always 1.0 per project convention
                response_mime_type="application/json",
            ),
        )

        options_data = json.loads(response.text)
        options = options_data.get("options", [])

        logger.info(f"Generated {len(options)} {request.story_type} options")

        # Add the custom option (this is the only static part - it's UI chrome)
        custom_option = {
            "emoji": "✨",
            "label": "My own idea...",
            "beats": None if request.story_type == "manga" else None,
            "description": None if request.story_type == "scene" else None
        }

        return GenerateStoryOptionsResponse(
            story_type=request.story_type,
            character_name=request.character_name,
            options=options,
            custom_option=custom_option
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse story options")
    except Exception as e:
        logger.error(f"Failed to generate story options: {e}")
        raise HTTPException(status_code=500, detail=f"Story options generation failed: {str(e)}")


# =============================================================================
# Static Files
# =============================================================================

# Mount assets directory for demo photos and generated outputs
# Generated images are stored in assets/outputs/characters/
assets_dir = Path(__file__).parent.parent / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

# Mount agent directory for ES module imports
agent_dir = Path(__file__).parent.parent / "agent"
if agent_dir.exists():
    app.mount("/agent", StaticFiles(directory=str(agent_dir)), name="agent")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("Creative Universe API Server")
    print("=" * 60)
    print(f"Model: {GEMINI_MODEL}")
    print(f"Demo UI: http://localhost:8000/")
    print(f"API Docs: http://localhost:8000/docs")
    print("=" * 60 + "\n")

    is_production = os.getenv("VIBECUT_ENV") == "production"
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=not is_production,
        workers=2 if is_production else 1,
    )
